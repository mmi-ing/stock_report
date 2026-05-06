"""Stock Lab CLI — Typer 엔트리.

사용 예:
    python -m stocklab NVDA
    python -m stocklab "소부장 추천"
    python -m stocklab "NVDA vs AMD"

이 골격은 라우터까지만 연결되어 있고 데이터/렌더는 다음 단계에서 채운다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import typer

from stocklab.router import parse

app = typer.Typer(add_completion=False, help="Stock Lab — 종목 분석 & 발굴 리포트 생성기")


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
    """입력을 받아 모드 분기 후 리포트를 생성한다 (Step 1: 라우터 결과 출력만)."""
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

    typer.echo(f"[mode {spec.mode}] {raw}")
    if spec.mode == "A":
        typer.echo(f"  ticker={spec.ticker}  class={spec.asset_class}  name={spec.display_name}")
    elif spec.mode == "B":
        typer.echo(f"  theme={spec.theme}  candidates={spec.candidates}")
    elif spec.mode == "C":
        typer.echo(f"  left={spec.left}  right={spec.right}")
    if spec.weights:
        typer.echo(f"  weights={spec.weights}")

    typer.echo(f"  out_dir={out}  no_llm={no_llm}  open={open_browser}")
    typer.echo("(Step 1: skeleton — 데이터/렌더는 다음 단계에서)")


if __name__ == "__main__":
    app()
