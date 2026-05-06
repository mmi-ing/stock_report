"""기술적 지표 — pandas/numpy 만으로 결정론적 구현.

EMA / RSI(14) / MACD(12,26,9) 는 pandas .ewm 와 일치하도록 작성.
매물대(volume profile) 는 가격 빈별 거래량 합으로 계산.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    """지수 이동 평균 — pandas ewm(span, adjust=False) 와 동일."""
    return series.ewm(span=span, adjust=False).mean()


def rsi14(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI. ta-lib / TradingView 표준과 일치 (RMA = ewm alpha=1/period)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    # 0/0 → NaN (정의 안 됨), 양수/0 → inf → RSI = 100
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, Signal line, Histogram."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


@dataclass
class VolumeBin:
    price_low: float
    price_high: float
    volume: float
    pct: float  # 0~1, 전체 대비 비중

    @property
    def mid(self) -> float:
        return (self.price_low + self.price_high) / 2


def volume_profile(ohlc: pd.DataFrame, bins: int = 12) -> list[VolumeBin]:
    """OHLC 데이터로 가격 구간별 거래량 누적 (TPO 단순화).

    각 캔들의 (H+L)/2 가격이 어느 빈에 속하는지 보고 거래량을 누적한다.
    """
    if ohlc.empty or "V" not in ohlc.columns:
        return []
    if {"H", "L"}.issubset(ohlc.columns):
        prices = (ohlc["H"] + ohlc["L"]) / 2
    elif "C" in ohlc.columns:
        prices = ohlc["C"]
    else:
        return []
    p_min, p_max = float(prices.min()), float(prices.max())
    if p_max <= p_min:
        return []
    edges = np.linspace(p_min, p_max, bins + 1)
    vol = ohlc["V"].astype(float).to_numpy()
    idx = np.clip(np.digitize(prices.to_numpy(), edges) - 1, 0, bins - 1)
    bucket = np.zeros(bins, dtype=float)
    for i, v in zip(idx, vol):
        bucket[int(i)] += float(v)
    total = bucket.sum() or 1.0
    out: list[VolumeBin] = []
    for i in range(bins):
        out.append(
            VolumeBin(
                price_low=float(edges[i]),
                price_high=float(edges[i + 1]),
                volume=float(bucket[i]),
                pct=float(bucket[i] / total),
            )
        )
    return out


@dataclass
class IndicatorBundle:
    """차트와 지표 패널이 사용하는 한 종목 분량의 지표 묶음."""

    close: pd.Series
    ema5: pd.Series
    ema20: pd.Series
    ema60: pd.Series
    ema120: pd.Series
    rsi: pd.Series
    macd_line: pd.Series
    macd_signal: pd.Series
    macd_hist: pd.Series
    vol_profile: list[VolumeBin]

    def latest(self) -> dict[str, float | None]:
        def last(s: pd.Series) -> float | None:
            if s.empty:
                return None
            v = s.iloc[-1]
            return None if pd.isna(v) else float(v)

        return {
            "close": last(self.close),
            "ema5": last(self.ema5),
            "ema20": last(self.ema20),
            "ema60": last(self.ema60),
            "ema120": last(self.ema120),
            "rsi": last(self.rsi),
            "macd": last(self.macd_line),
            "signal": last(self.macd_signal),
            "hist": last(self.macd_hist),
        }


def compute(ohlc: pd.DataFrame) -> IndicatorBundle:
    """OHLC 한 묶음에서 모든 지표를 한 번에 계산."""
    close = ohlc["C"]
    macd_line, sig, hist = macd(close)
    return IndicatorBundle(
        close=close,
        ema5=ema(close, 5),
        ema20=ema(close, 20),
        ema60=ema(close, 60),
        ema120=ema(close, 120),
        rsi=rsi14(close),
        macd_line=macd_line,
        macd_signal=sig,
        macd_hist=hist,
        vol_profile=volume_profile(ohlc),
    )
