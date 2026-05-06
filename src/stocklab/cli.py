"""Stock Lab CLI — Typer 엔트리.

사용 예:
    python -m stocklab NVDA
    python -m stocklab "소부장 추천"
    python -m stocklab "NVDA vs AMD"
"""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

import typer

from stocklab import indicators, output
from stocklab.analysts import stock as analyst_stock
from stocklab.data import yahoo
from stocklab.render import renderer
from stocklab.router import RouteSpec, parse

app = typer.Typer(add_completion=False, help="Stock Lab — 종목 분석 & 발굴 리포트 생성기")


def _run_mode_a(spec: RouteSpec, no_llm: bool, out_dir: Path, open_browser: bool) -> int:
    assert spec.ticker and spec.asset_class
    typer.echo(f"[Mode A] {spec.ticker} 데이터 수집 중...")

    if spec.asset_class == "kr_stock" and "." not in spec.ticker:
        snap = yahoo.fetch_kr_with_fallback(spec.ticker)
    elif spec.asset_class == "kr_stock" and spec.ticker.endswith(".KS"):
        # .KS 시도 후 실패 시 .KQ
        snap = yahoo.fetch(spec.ticker, spec.asset_class)
        if snap.price is None:
            base = spec.ticker.replace(".KS", "")
            kq = yahoo.fetch(f"{base}.KQ", spec.asset_class)
            if kq.price is not None:
                snap = kq
    else:
        snap = yahoo.fetch(spec.ticker, spec.asset_class)

    if snap.price is None and snap.ohlc.empty:
        typer.echo(f"[error] {spec.ticker} 데이터를 가져오지 못했습니다.", err=True)
        if snap.fetch_warnings:
            for w in snap.fetch_warnings:
                typer.echo(f"  · {w}", err=True)
        return 1

    typer.echo(f"  → 가격 {snap.price} {snap.currency}, OHLC {len(snap.ohlc)}주")
    typer.echo("[Mode A] 지표 계산 중...")
    ind = indicators.compute(snap.ohlc) if not snap.ohlc.empty else None

    if ind is None:
        typer.echo("[error] OHLC 데이터가 없어 지표 계산 불가.", err=True)
        return 1

    typer.echo("[Mode A] HTML 렌더링 중...")
    if no_llm:
        typer.echo("  → narrative 결정론 폴백 (--no-llm)")
        ctx = analyst_stock.build_context(snap, ind, weights=spec.weights)
    else:
        # Step 4 에서 narrative LLM 호출 추가됨
        ctx = analyst_stock.build_context(snap, ind, weights=spec.weights)

    html = renderer.render("mode_a.html.j2", ctx)
    path = output.save(html, key=spec.display_name or spec.ticker, out_dir=out_dir)
    typer.echo(f"[ok] {path}")

    if open_browser:
        webbrowser.open(path.resolve().as_uri())
    return 0


@app.command()
def main(
    query: list[str] = typer.Argument(..., help="티커, 회사명, 테마, 또는 'X vs Y'"),
    out: Path = typer.Option(Path("output"), "--out", "-o", help="HTML 출력 디렉터리"),
    no_llm: bool = typer.Option(False, "--no-llm", help="narrative 결정론 폴백 사용"),
    open_browser: bool = typer.Option(False, "--open", help="생성 후 브라우저로 열기"),
    short: bool = typer.Option(False, "--short", help="단기 트레이딩 가중"),
    aggressive: bool = typer.Option(False, "--aggressive", help="공격적 (모드 B)"),
    conservative: bool = typer.Option(False, "--conservative", help="보수적 (모드 B)"),
) -> None:
    raw = " ".join(query)
    spec = parse(raw)

    extra: list[str] = []
    if short:
        extra.append("short")
    if aggressive:
        extra.append("aggressive")
    if conservative:
        extra.append("conservative")
    spec.weights.extend(extra)

    if spec.mode == "ambiguous":
        typer.echo(f"[ambiguous] '{raw}' 가 모호합니다.", err=True)
        for line in spec.ambiguous_options:
            typer.echo(f"  - {line}", err=True)
        raise typer.Exit(code=2)

    if spec.mode == "A":
        rc = _run_mode_a(spec, no_llm=no_llm, out_dir=out, open_browser=open_browser)
        raise typer.Exit(code=rc)
    elif spec.mode == "B":
        typer.echo(f"[Mode B] theme={spec.theme} candidates={spec.candidates}")
        typer.echo("(Mode B 구현은 Step 5)")
        raise typer.Exit(code=0)
    elif spec.mode == "C":
        typer.echo(f"[Mode C] {spec.left} vs {spec.right}")
        typer.echo("(Mode C 구현은 Step 6)")
        raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
