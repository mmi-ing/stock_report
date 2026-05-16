"""사용자 검색어 → stocklab 리포트 → 텔레그램 전송."""
from __future__ import annotations

import asyncio
import io
from pathlib import Path

from telegram import Update, InputFile
from telegram.ext import ContextTypes

from stocklab import indicators
from stocklab.analysts import stock as analyst_stock
from stocklab.data import yahoo
from stocklab.render import renderer
from stocklab.router import parse


def _build_text_summary(ctx: dict) -> str:
    """리포트의 핵심 수치를 텔레그램 텍스트로 요약."""
    name = ctx.get("display_name") or ctx.get("ticker")
    sym = ctx.get("price_symbol", "$")
    price = ctx.get("price")
    krw = ctx.get("krw_price_str", "")
    change = ctx.get("change_str", "")
    cap = ctx.get("market_cap_str", "N/A")
    pe = ctx.get("pe_forward_str", "N/A")
    rsi = ctx.get("indicator_panel", {}).get("rsi", {}).get("value", "N/A")

    quality = ctx.get("quality", {})
    analyst = ctx.get("analyst_box", {})
    trading = ctx.get("trading_box", {})
    verdict = ctx.get("verdict", {})

    lines = [
        f"📊 *{name}* ({ctx.get('ticker')})",
        f"가격: {sym}{price:,.2f} {change}" if price else f"가격: N/A",
    ]
    if krw:
        lines.append(f"환산: ≈ {krw}")
    lines += [
        "",
        f"시총: {cap}  |  P/E: {pe}  |  RSI: {rsi}",
        f"ROE: {quality.get('roe_str','N/A')}  |  PEG: {quality.get('peg_str','N/A')}",
    ]
    if analyst.get("n_analysts"):
        lines.append(
            f"애널 {analyst['n_analysts']}명: {analyst.get('rec_label','')} "
            f"목표가 {analyst.get('mean_str','N/A')} ({analyst.get('upside_str','')})"
        )
    lines += [
        f"52주 위치 {trading.get('pos_52w_pct','N/A')} | ATR {trading.get('atr_str','N/A')} | 거래량 {trading.get('vol_spike_str','N/A')}",
    ]
    if verdict:
        lines += ["", f"🎯 *결론*: {verdict.get('text', '')}"]
    return "\n".join(lines)


async def _generate_report(query: str) -> tuple[str, str, str] | None:
    """동기 분석을 별도 스레드에서 실행. 반환: (text_summary, html, display_name)."""
    spec = parse(query.strip())
    if spec.mode == "ambiguous":
        opts = "\n".join(f"  • {o}" for o in spec.ambiguous_options)
        return (f"❓ '{query}' 가 모호합니다.\n{opts}", "", query)

    if spec.mode == "A":
        if not spec.ticker or not spec.asset_class:
            return None
        if spec.asset_class == "kr_stock" and "." not in spec.ticker:
            snap = yahoo.fetch_kr_with_fallback(spec.ticker)
        else:
            snap = yahoo.fetch(spec.ticker, spec.asset_class)
        if snap.price is None and snap.ohlc.empty:
            return (f"❌ '{query}' 데이터를 가져오지 못했습니다.", "", query)
        ind = indicators.compute(snap.ohlc) if not snap.ohlc.empty else None
        if ind is None:
            return (f"❌ OHLC 부족으로 분석 불가.", "", query)
        ctx = analyst_stock.build_context(snap, ind, weights=spec.weights)
        html = renderer.render("mode_a.html.j2", ctx)
        return (_build_text_summary(ctx), html, snap.name or spec.ticker)

    if spec.mode == "B":
        from stocklab.analysts import theme as analyst_theme
        ctx = analyst_theme.build_context(
            theme=spec.theme or query, candidates=spec.candidates, weights=spec.weights
        )
        html = renderer.render("mode_b.html.j2", ctx)
        return (f"📊 테마 '{ctx.get('theme_label', query)}' 분석 완료. HTML 첨부.", html, spec.theme or query)

    if spec.mode == "C":
        from stocklab.analysts import compare as analyst_compare
        ctx = analyst_compare.build_context(
            left_raw=spec.left or "", right_raw=spec.right or "", weights=spec.weights
        )
        html = renderer.render("mode_c.html.j2", ctx)
        return (f"⚖️ 비교 분석 완료. HTML 첨부.", html, f"{spec.left}_vs_{spec.right}")

    return None


async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return
    query = msg.text.strip().lstrip("/")
    if not query:
        return

    placeholder = await msg.reply_text(f"🔍 '{query}' 분석 중...")

    try:
        result = await asyncio.to_thread(_run_sync, query)
    except Exception as e:
        await placeholder.edit_text(f"❌ 에러: {e}")
        return

    if result is None:
        await placeholder.edit_text("❌ 분석 실패")
        return

    text, html, display_name = result
    await placeholder.edit_text(text, parse_mode="Markdown")

    if html:
        # HTML 파일 첨부
        buf = io.BytesIO(html.encode("utf-8"))
        buf.name = f"{display_name.replace(' ', '_')}.html"
        await msg.reply_document(
            document=InputFile(buf, filename=buf.name),
            caption="📎 HTML 리포트 (다운로드 후 브라우저로 열기)",
        )


def _run_sync(query: str):
    """동기 wrapper — asyncio.to_thread 안에서 호출."""
    return asyncio.run(_generate_report(query))
