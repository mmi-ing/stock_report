"""모드 C — 두 종목 비교 분석.

기존 mode A 의 데이터·지표 파이프라인을 재사용해 좌우 2컬럼으로 구성.
README §7 의 우월성 매트릭스 (매출 성장 / 이익률 / 부채 / 모멘텀 / 밸류에이션 /
배당 / 미래 전망) 를 코드로 점수화한다.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

import pandas as pd

from stocklab.config import KR_NAME_TO_TICKER, PALETTE, ETF_TICKERS
from stocklab.data import yahoo
from stocklab.data.yahoo import StockSnapshot
from stocklab.indicators import IndicatorBundle, compute, rsi14

RE_US_TICKER = re.compile(r"^[A-Z]{1,5}$")
RE_KR_CODE = re.compile(r"^\d{6}$")
RE_KR_SUFFIX = re.compile(r"^\d{6}\.(KS|KQ)$", re.IGNORECASE)
RE_CRYPTO = re.compile(r"^[A-Z0-9]{2,6}-USD$", re.IGNORECASE)


@dataclass
class CompareSide:
    """한쪽 종목 분량의 비교용 데이터."""

    ticker: str
    name: str
    exchange: str
    currency: str
    price_str: str
    price_symbol: str
    change_str: str
    change_pos: bool
    market_cap_str: str
    pe_forward: float | None
    pe_str: str
    ps_str: str
    div_yield: float | None
    div_str: str
    revenue_yoy: float | None
    revenue_yoy_str: str
    operating_margin: float | None
    operating_margin_str: str
    debt_to_equity: float | None
    debt_to_equity_str: str
    rsi: float | None
    rsi_str: str
    return_period: float | None  # 보유기간 수익률
    return_str: str
    chart_labels: list[str]
    chart_close: list[float]
    chart_ema20: list[float | None]


@dataclass
class MatrixItem:
    label: str
    left_value: str
    right_value: str
    winner: Literal["left", "right", "tie"]


def _resolve_to_ticker(text: str) -> tuple[str, str]:
    """입력 한 토막을 티커로 정규화. (ticker, asset_class)."""
    t = text.strip()
    if RE_CRYPTO.match(t):
        return t.upper(), "crypto"
    if RE_KR_SUFFIX.match(t):
        return t.upper(), "kr_stock"
    if RE_KR_CODE.match(t):
        return f"{t}.KS", "kr_stock"
    if RE_US_TICKER.match(t):
        if t in ETF_TICKERS:
            return t, "etf"
        return t, "us_stock"
    # 한국 회사명
    for name in sorted(KR_NAME_TO_TICKER.keys(), key=len, reverse=True):
        if name in t:
            return KR_NAME_TO_TICKER[name], "kr_stock"
    return t, "us_stock"


def _fetch_with_kr_fallback(ticker: str, asset_class: str) -> StockSnapshot:
    if asset_class == "kr_stock" and ticker.endswith(".KS"):
        snap = yahoo.fetch(ticker, asset_class)  # type: ignore[arg-type]
        if snap.price is None:
            kq = yahoo.fetch(ticker.replace(".KS", ".KQ"), "kr_stock")
            if kq.price is not None:
                return kq
        return snap
    return yahoo.fetch(ticker, asset_class)  # type: ignore[arg-type]


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


def _build_side(snap: StockSnapshot, ind: IndicatorBundle) -> CompareSide:
    p = float(snap.price) if snap.price else None
    sym = "₩" if snap.currency == "KRW" else "$"
    if p is None:
        price_str = "N/A"
    elif snap.currency == "KRW":
        price_str = f"{p:,.0f}"
    else:
        price_str = f"{p:,.2f}"

    change_pct = snap.change_pct
    change_str = "N/A" if change_pct is None else f"{'+' if change_pct >= 0 else ''}{change_pct:.2f}%"

    fin = snap.financials
    rev_yoy = fin.revenue_yoy
    om = fin.operating_margin
    de = fin.debt_to_equity
    div = snap.div_yield

    if not snap.ohlc.empty and "C" in snap.ohlc.columns:
        first = float(snap.ohlc["C"].iloc[0])
        last = p if p is not None else float(snap.ohlc["C"].iloc[-1])
        return_period = (last - first) / first if first else None
    else:
        return_period = None
    return_str = "N/A" if return_period is None else f"{'+' if return_period >= 0 else ''}{return_period*100:.1f}%"

    rsi_val = ind.latest().get("rsi") if ind else None
    rsi_str = "N/A" if rsi_val is None or pd.isna(rsi_val) else f"{rsi_val:.1f}"

    labels = [d.strftime("%b W%U") for d in snap.ohlc.index] if not snap.ohlc.empty else []
    closes = [float(v) for v in snap.ohlc["C"].tolist()] if not snap.ohlc.empty else []
    ema20 = [None if pd.isna(v) else float(v) for v in ind.ema20.tolist()] if ind else []

    return CompareSide(
        ticker=snap.ticker,
        name=snap.name,
        exchange=snap.exchange or "N/A",
        currency=snap.currency,
        price_str=price_str,
        price_symbol=sym,
        change_str=change_str,
        change_pos=(change_pct is not None and change_pct >= 0),
        market_cap_str=_scale_money(snap.market_cap, snap.currency),
        pe_forward=snap.pe_forward,
        pe_str=f"{snap.pe_forward:.2f}" if snap.pe_forward else "N/A",
        ps_str=f"{snap.ps_ttm:.2f}" if snap.ps_ttm else "N/A",
        div_yield=div,
        div_str=f"{div*100:.2f}%" if div else "N/A",
        revenue_yoy=rev_yoy,
        revenue_yoy_str=f"{rev_yoy*100:+.1f}%" if rev_yoy is not None else "N/A",
        operating_margin=om,
        operating_margin_str=f"{om*100:.1f}%" if om is not None else "N/A",
        debt_to_equity=de,
        debt_to_equity_str=f"{de:.1f}" if de is not None else "N/A",
        rsi=None if rsi_val is None or pd.isna(rsi_val) else float(rsi_val),
        rsi_str=rsi_str,
        return_period=return_period,
        return_str=return_str,
        chart_labels=labels,
        chart_close=closes,
        chart_ema20=ema20,
    )


def _winner(left: float | None, right: float | None, higher_is_better: bool = True) -> Literal["left", "right", "tie"]:
    if left is None and right is None:
        return "tie"
    if left is None:
        return "right"
    if right is None:
        return "left"
    if abs(left - right) < 1e-9:
        return "tie"
    if higher_is_better:
        return "left" if left > right else "right"
    return "left" if left < right else "right"


def _build_matrix(L: CompareSide, R: CompareSide) -> list[MatrixItem]:
    return [
        MatrixItem("매출 성장 (YoY)", L.revenue_yoy_str, R.revenue_yoy_str,
                   _winner(L.revenue_yoy, R.revenue_yoy, higher_is_better=True)),
        MatrixItem("영업이익률", L.operating_margin_str, R.operating_margin_str,
                   _winner(L.operating_margin, R.operating_margin, higher_is_better=True)),
        MatrixItem("부채비율 (D/E)", L.debt_to_equity_str, R.debt_to_equity_str,
                   _winner(L.debt_to_equity, R.debt_to_equity, higher_is_better=False)),
        MatrixItem("모멘텀 (RSI)", L.rsi_str, R.rsi_str,
                   _winner(L.rsi, R.rsi, higher_is_better=True)),
        MatrixItem("밸류에이션 (Fwd P/E)", L.pe_str, R.pe_str,
                   _winner(L.pe_forward, R.pe_forward, higher_is_better=False)),
        MatrixItem("배당", L.div_str, R.div_str,
                   _winner(L.div_yield, R.div_yield, higher_is_better=True)),
        MatrixItem("보유기간 수익률", L.return_str, R.return_str,
                   _winner(L.return_period, R.return_period, higher_is_better=True)),
    ]


def _final_recommendation(matrix: list[MatrixItem], L: CompareSide, R: CompareSide) -> dict[str, str]:
    left_wins = sum(1 for m in matrix if m.winner == "left")
    right_wins = sum(1 for m in matrix if m.winner == "right")
    diff = left_wins - right_wins

    if diff >= 3:
        weight = f"{L.ticker} 7 : {R.ticker} 3"
        verdict = f"{L.ticker} 우세 — 7:3 비중 추천"
    elif diff >= 1:
        weight = f"{L.ticker} 6 : {R.ticker} 4"
        verdict = f"{L.ticker} 약간 우세 — 6:4 비중"
    elif diff <= -3:
        weight = f"{L.ticker} 3 : {R.ticker} 7"
        verdict = f"{R.ticker} 우세 — 3:7 비중 추천"
    elif diff <= -1:
        weight = f"{L.ticker} 4 : {R.ticker} 6"
        verdict = f"{R.ticker} 약간 우세 — 4:6 비중"
    else:
        weight = f"{L.ticker} 5 : {R.ticker} 5"
        verdict = "양쪽 균형 — 5:5 비중 분산 권장"

    left_case = (
        f"{L.ticker} 가 적합한 경우: 펀더멘털 강점 (성장·이익률) 또는 모멘텀 우위가 명확할 때."
    )
    right_case = (
        f"{R.ticker} 가 적합한 경우: 밸류에이션 매력 또는 배당·안정성을 우선할 때."
    )
    return {
        "weight": weight,
        "verdict": verdict,
        "left_case": left_case,
        "right_case": right_case,
        "left_wins": str(left_wins),
        "right_wins": str(right_wins),
    }


def build_context(left_raw: str, right_raw: str, weights: list[str] | None = None) -> dict[str, Any]:
    weights = weights or []
    l_tk, l_cls = _resolve_to_ticker(left_raw)
    r_tk, r_cls = _resolve_to_ticker(right_raw)

    with ThreadPoolExecutor(max_workers=2) as exe:
        l_fut = exe.submit(_fetch_with_kr_fallback, l_tk, l_cls)
        r_fut = exe.submit(_fetch_with_kr_fallback, r_tk, r_cls)
        l_snap = l_fut.result()
        r_snap = r_fut.result()

    if l_snap.price is None and l_snap.ohlc.empty:
        raise RuntimeError(f"좌측 종목 '{left_raw}' 데이터 수집 실패")
    if r_snap.price is None and r_snap.ohlc.empty:
        raise RuntimeError(f"우측 종목 '{right_raw}' 데이터 수집 실패")

    l_ind = compute(l_snap.ohlc) if not l_snap.ohlc.empty else None
    r_ind = compute(r_snap.ohlc) if not r_snap.ohlc.empty else None

    L = _build_side(l_snap, l_ind) if l_ind else None
    R = _build_side(r_snap, r_ind) if r_ind else None
    if L is None or R is None:
        raise RuntimeError("OHLC 데이터 부족으로 비교 불가")

    matrix = _build_matrix(L, R)
    final = _final_recommendation(matrix, L, R)

    return {
        "display_name": f"{L.ticker} vs {R.ticker}",
        "left": asdict(L),
        "right": asdict(R),
        "matrix": [asdict(m) for m in matrix],
        "final": final,
        "generated_at": datetime.now().strftime("%Y.%m.%d"),
        "sources": ["Yahoo Finance"],
        "palette": PALETTE,
        "weights": weights,
    }
