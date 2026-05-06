"""모드 B — 테마 발굴(스크리닝).

후보 종목들을 병렬로 fetch → 모멘텀 점수 산정 → 매트릭스 + Top3 + 4그룹 분류.
README §6 (7섹션 명세) 와 §10·§11 (테마 사전) 을 코드로 구현.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from stocklab.config import PALETTE
from stocklab.data import yahoo
from stocklab.data.yahoo import StockSnapshot


@dataclass
class MatrixRow:
    rank: int
    ticker: str
    name: str
    market: str
    market_cap_str: str
    return_1y_str: str
    pe_forward_str: str
    momentum: float
    momentum_color: str  # green/yellow/red
    stars: str           # ★★★ / ★★ / ★


@dataclass
class TopPick:
    rank: int  # 1, 2, 3
    medal: str  # gold/silver/bronze
    ticker: str
    name: str
    headline: str
    reasons: list[str]
    entry_str: str
    target_str: str
    risk_str: str


@dataclass
class GroupCard:
    icon: str
    title: str
    stocks: list[dict]  # {ticker, name, blurb}
    comment: str


def _fetch_safely(ticker: str) -> StockSnapshot | None:
    asset_class = (
        "kr_stock" if ticker.endswith((".KS", ".KQ"))
        else "crypto" if ticker.endswith("-USD")
        else "us_stock"
    )
    try:
        snap = yahoo.fetch(ticker, asset_class)  # type: ignore[arg-type]
        if snap.price is None and snap.ohlc.empty:
            return None
        return snap
    except Exception:
        return None


def _return_1y(snap: StockSnapshot) -> float | None:
    """26주봉(약 6개월) OHLC 만 갖고 있으므로 보유 기간 수익률만 계산.

    더 긴 기간은 yfinance.history(period='1y') 별도 호출이 필요하지만, 매트릭스 표에서
    화면에 표시되는 수익률은 'OHLC 첫 종가 → 현재가' 로 충분히 대용 가능.
    """
    if snap.ohlc.empty or "C" not in snap.ohlc.columns:
        return None
    first_close = float(snap.ohlc["C"].iloc[0])
    last_close = float(snap.price) if snap.price else float(snap.ohlc["C"].iloc[-1])
    if first_close == 0:
        return None
    return (last_close - first_close) / first_close


def _rsi_latest(snap: StockSnapshot) -> float | None:
    if snap.ohlc.empty or len(snap.ohlc) < 15:
        return None
    from stocklab.indicators import rsi14
    val = rsi14(snap.ohlc["C"]).iloc[-1]
    return None if pd.isna(val) else float(val)


def _momentum_score(snap: StockSnapshot) -> float:
    """0~10 점 — 1Y 수익률(40%) + RSI 건강도(20%) + Forward P/E 적정성(20%) + 매출성장(20%)."""
    score = 5.0
    ret = _return_1y(snap)
    if ret is not None:
        # +50% → +2, -50% → -2 클립
        score += max(-2.5, min(2.5, ret * 5))
    rsi = _rsi_latest(snap)
    if rsi is not None:
        if 40 <= rsi <= 70:
            score += 1.0
        elif 30 <= rsi < 40 or 70 < rsi <= 80:
            score += 0.0
        else:
            score -= 1.0
    pe = snap.pe_forward
    if pe is not None:
        if 5 <= pe <= 25:
            score += 1.0
        elif pe > 50 or pe < 0:
            score -= 1.0
    rev_g = snap.financials.revenue_yoy
    if rev_g is not None:
        score += max(-1.5, min(1.5, rev_g * 3))
    return max(0.0, min(10.0, score))


def _color_for(score: float) -> str:
    if score >= 8.0:
        return "green"
    if score >= 6.0:
        return "yellow"
    return "red"


def _stars(score: float) -> str:
    if score >= 7.5:
        return "★★★"
    if score >= 5.5:
        return "★★"
    return "★"


def _market(snap: StockSnapshot) -> str:
    if snap.asset_class == "kr_stock":
        return "KOSPI" if snap.ticker.endswith(".KS") else "KOSDAQ"
    if snap.asset_class == "crypto":
        return "Crypto"
    if snap.asset_class == "etf":
        return "ETF"
    return "US"


def _scale_money(v: float | None, currency: str) -> str:
    if v is None:
        return "N/A"
    if currency == "KRW":
        if v >= 1e12:
            return f"{v/1e12:.2f}조"
        if v >= 1e8:
            return f"{v/1e8:.0f}억"
        return f"{v:,.0f}"
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"


def _build_matrix(snaps: list[StockSnapshot]) -> list[MatrixRow]:
    rows: list[MatrixRow] = []
    scored: list[tuple[float, StockSnapshot]] = [
        (_momentum_score(s), s) for s in snaps if s is not None
    ]
    scored.sort(key=lambda t: t[0], reverse=True)
    for i, (score, s) in enumerate(scored, 1):
        ret = _return_1y(s)
        ret_str = f"{ret*100:+.1f}%" if ret is not None else "N/A"
        rows.append(
            MatrixRow(
                rank=i,
                ticker=s.ticker,
                name=s.name,
                market=_market(s),
                market_cap_str=_scale_money(s.market_cap, s.currency),
                return_1y_str=ret_str,
                pe_forward_str=f"{s.pe_forward:.1f}" if s.pe_forward else "N/A",
                momentum=score,
                momentum_color=_color_for(score),
                stars=_stars(score),
            )
        )
    return rows


def _build_top3(matrix: list[MatrixRow], snaps_by_ticker: dict[str, StockSnapshot]) -> list[TopPick]:
    picks: list[TopPick] = []
    medals = ["gold", "silver", "bronze"]
    for i, row in enumerate(matrix[:3]):
        snap = snaps_by_ticker.get(row.ticker)
        if not snap:
            continue
        p = float(snap.price) if snap.price else 0.0
        sym = "₩" if snap.currency == "KRW" else "$"
        if snap.currency == "KRW":
            entry = f"{sym}{p*0.97:,.0f}~{sym}{p*1.03:,.0f}"
            target = f"{sym}{p*1.20:,.0f}~{sym}{p*1.40:,.0f}"
            stop = f"{sym}{p*0.85:,.0f}"
        else:
            entry = f"{sym}{p*0.97:,.2f}~{sym}{p*1.03:,.2f}"
            target = f"{sym}{p*1.20:,.2f}~{sym}{p*1.40:,.2f}"
            stop = f"{sym}{p*0.85:,.2f}"

        reasons = []
        ret = _return_1y(snap)
        if ret is not None and ret > 0:
            reasons.append(f"보유기간 수익률 {ret*100:+.1f}% — 추세 유효")
        if snap.financials.revenue_yoy and snap.financials.revenue_yoy > 0.1:
            reasons.append(f"매출 YoY {snap.financials.revenue_yoy*100:.1f}% — 성장세")
        if snap.pe_forward and 5 <= snap.pe_forward <= 25:
            reasons.append(f"Forward P/E {snap.pe_forward:.1f} — 밸류에이션 적정")
        if not reasons:
            reasons.append("종합 모멘텀 점수 상위")
        reasons = reasons[:4]

        picks.append(
            TopPick(
                rank=i + 1,
                medal=medals[i],
                ticker=snap.ticker,
                name=snap.name,
                headline=f"{snap.industry or snap.sector or '핵심'} 섹터 모멘텀 상위",
                reasons=reasons,
                entry_str=f"진입 {entry}",
                target_str=f"3년 목표 {target}",
                risk_str=f"손절 {stop} 이하",
            )
        )
    return picks


def _build_groups(snaps: list[StockSnapshot]) -> list[GroupCard]:
    valid = [s for s in snaps if s is not None and s.price is not None]
    if not valid:
        return []
    by_cap = sorted(valid, key=lambda s: s.market_cap or 0, reverse=True)[:3]
    by_growth = sorted(
        [s for s in valid if s.financials.revenue_yoy is not None],
        key=lambda s: s.financials.revenue_yoy or 0,
        reverse=True,
    )[:3]
    by_value = sorted(
        [s for s in valid if s.pe_forward is not None and s.pe_forward > 0],
        key=lambda s: s.pe_forward or 999,
    )[:3]
    by_div = sorted(
        [s for s in valid if s.div_yield is not None],
        key=lambda s: s.div_yield or 0,
        reverse=True,
    )[:3]

    def _to_dicts(stocks: list[StockSnapshot], blurb_fn) -> list[dict]:
        return [{"ticker": s.ticker, "name": s.name, "blurb": blurb_fn(s)} for s in stocks]

    groups = [
        GroupCard("🏛️", "대장주", _to_dicts(by_cap, lambda s: _scale_money(s.market_cap, s.currency)),
                  "시총 상위 — 안정성"),
        GroupCard("🚀", "성장주",
                  _to_dicts(by_growth, lambda s: f"매출 YoY {(s.financials.revenue_yoy or 0)*100:+.1f}%"),
                  "높은 매출 성장률"),
        GroupCard("💎", "가치주",
                  _to_dicts(by_value, lambda s: f"Fwd P/E {s.pe_forward:.1f}"),
                  "낮은 Forward P/E"),
        GroupCard("💰", "배당주",
                  _to_dicts(by_div, lambda s: f"배당률 {(s.div_yield or 0)*100:.2f}%"),
                  "배당수익률 상위"),
    ]
    return groups


def _theme_aggregate(snaps: list[StockSnapshot]) -> dict[str, Any]:
    valid = [s for s in snaps if s is not None and s.price is not None]
    total_cap = sum(s.market_cap or 0 for s in valid)
    pes = [s.pe_forward for s in valid if s.pe_forward and s.pe_forward > 0]
    avg_pe = sum(pes) / len(pes) if pes else None
    rets = [_return_1y(s) for s in valid]
    rets = [r for r in rets if r is not None]
    avg_ret = sum(rets) / len(rets) if rets else None
    momentums = [_momentum_score(s) for s in valid]
    avg_mom = sum(momentums) / len(momentums) if momentums else 5.0
    currency = valid[0].currency if valid else "USD"
    return {
        "total_cap_str": _scale_money(total_cap, currency),
        "avg_pe_str": f"{avg_pe:.1f}" if avg_pe else "N/A",
        "avg_return_1y_str": f"{avg_ret*100:+.1f}%" if avg_ret is not None else "N/A",
        "policy_score": "8 / 10",  # TODO: Step 7 에서 정책/매크로 모듈로 보강
        "momentum_score": f"{avg_mom:.1f} / 10",
        "stock_count": len(valid),
        "currency": currency,
    }


def _verdict_for_theme(avg_mom: float, avg_ret: float | None, weights: list[str]) -> dict[str, str]:
    if "aggressive" in weights and avg_mom >= 6:
        return {"label": "★ 적극 비중 확대 ★", "sub": "공격적 옵션 — Top3 비중 확대"}
    if avg_mom >= 7.5:
        return {"label": "★ 적극 비중 확대 ★", "sub": "테마 모멘텀 강세 + 정책 우호"}
    if avg_mom >= 6.0:
        return {"label": "★ 분할 매수 매력 ★", "sub": "장기 스토리 유효, 단기 변동 가능"}
    if avg_mom >= 4.5:
        return {"label": "⚠ 선별 매수 권장 ⚠", "sub": "Top1~2 종목만 선별"}
    return {"label": "🚫 회피 권장 🚫", "sub": "모멘텀 둔화 또는 과열"}


def build_context(theme: str, candidates: list[str], weights: list[str] | None = None) -> dict[str, Any]:
    weights = weights or []

    snaps: list[StockSnapshot] = []
    with ThreadPoolExecutor(max_workers=8) as exe:
        futures = {exe.submit(_fetch_safely, t): t for t in candidates}
        for f in as_completed(futures):
            s = f.result()
            if s is not None:
                snaps.append(s)

    matrix = _build_matrix(snaps)
    snaps_by_ticker = {s.ticker: s for s in snaps}
    top3 = _build_top3(matrix, snaps_by_ticker)
    groups = _build_groups(snaps)
    agg = _theme_aggregate(snaps)
    verdict = _verdict_for_theme(
        avg_mom=float(agg["momentum_score"].split(" ")[0]),
        avg_ret=None,
        weights=weights,
    )

    # 디폴트 비중 (README §종목 발굴 디폴트 성향)
    if "aggressive" in weights:
        portfolio_weight = "전체 자산의 7~12% (공격적)"
    elif "conservative" in weights:
        portfolio_weight = "전체 자산의 3~5% (보수적)"
    else:
        portfolio_weight = "전체 자산의 5~10% (밸런스)"

    overview = {
        "definition": f"'{theme}' 테마 — 후보 종목 {len(snaps)}개를 모멘텀·밸류·성장으로 종합 평가.",
        "size_growth": "테마 규모 / CAGR 정보는 매크로 모듈 보강 후 표시 (Step 7)",
        "policy_event": "정책·이벤트 데이터는 매크로 모듈 보강 예정",
        "global_trend": "글로벌 메가트렌드 연결성은 narrative 모듈에서 확장",
    }
    pos_tags = ["산업 정책 우호 (예시)", "글로벌 트렌드 부합 (예시)", "수출 모멘텀 (예시)"]
    neg_tags = ["원자재 변동성 (예시)", "환율 리스크 (예시)"]
    neu_tags = ["사이클 후반부 (예시)", "금리 변수 (예시)"]

    macro = {
        "currency_note": "환율 — 수출주는 KRW 약세 시 수혜, 강세 시 부담.",
        "rate_note": "금리 — 인하 사이클 시 성장주에 우호.",
        "policy_note": "정책 — 산업 지원·세제 혜택 모니터링.",
        "global_cycle": "글로벌 경기 — 회복 국면이면 비중 확대 매력.",
    }
    entry_strategy = {
        "now": "지금 — Top1 (Gold) 즉시 매수 가능 여부 확인.",
        "dip": "조정 시 (-10%) — Top2~3 추가 매수 가격대 진입.",
        "overheat": "과열 시 (+20%) — Gold/Silver 부분 익절, Bronze 회피.",
    }

    return {
        "theme": theme,
        "display_name": f"{theme} 테마",  # base.html.j2 의 title 태그용
        "header_meta": agg,
        "matrix": [asdict(r) for r in matrix],
        "top_picks": [asdict(p) for p in top3],
        "groups": [asdict(g) for g in groups],
        "overview": overview,
        "pos_tags": pos_tags,
        "neg_tags": neg_tags,
        "neu_tags": neu_tags,
        "macro": macro,
        "entry_strategy": entry_strategy,
        "verdict": verdict,
        "portfolio_weight": portfolio_weight,
        "generated_at": datetime.now().strftime("%Y.%m.%d"),
        "sources": ["Yahoo Finance"],
        "palette": PALETTE,
        "weights": weights,
    }
