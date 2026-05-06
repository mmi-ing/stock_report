"""indicators 골든 케이스 — pandas ewm 와 일치, 알려진 RSI/MACD 시퀀스로 검증."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stocklab.indicators import (
    IndicatorBundle,
    compute,
    ema,
    macd,
    rsi14,
    volume_profile,
)


def _close_series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


class TestEMA:
    def test_matches_pandas_ewm(self):
        s = _close_series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        expected = s.ewm(span=3, adjust=False).mean()
        got = ema(s, 3)
        pd.testing.assert_series_equal(got, expected)

    def test_constant_series_constant_ema(self):
        s = _close_series([5.0] * 20)
        out = ema(s, 5)
        assert (out == 5.0).all()

    def test_first_value_equals_input(self):
        s = _close_series([10, 20, 30])
        out = ema(s, 3)
        assert out.iloc[0] == 10.0


class TestRSI:
    def test_steady_uptrend_high_rsi(self):
        # 20주 단조 증가 → RSI 매우 높음 (70 초과)
        s = _close_series(list(range(100, 130)))
        r = rsi14(s)
        assert r.iloc[-1] > 70

    def test_steady_downtrend_low_rsi(self):
        s = _close_series(list(range(130, 100, -1)))
        r = rsi14(s)
        assert r.iloc[-1] < 30

    def test_flat_series_nan_or_50(self):
        # 변화 없음 → gain/loss 모두 0 → NaN (정의되지 않음)
        s = _close_series([100.0] * 20)
        r = rsi14(s)
        assert pd.isna(r.iloc[-1])

    def test_in_0_100_range(self):
        rng = np.random.default_rng(42)
        s = pd.Series(100 + rng.normal(0, 2, 100).cumsum())
        r = rsi14(s).dropna()
        assert (r >= 0).all() and (r <= 100).all()


class TestMACD:
    def test_returns_three_series(self):
        s = _close_series(list(range(1, 60)))
        m, sig, h = macd(s)
        assert len(m) == len(sig) == len(h) == 59

    def test_uptrend_macd_positive(self):
        s = _close_series([100 + i * 0.5 for i in range(60)])
        m, _, _ = macd(s)
        assert m.iloc[-1] > 0

    def test_histogram_equals_macd_minus_signal(self):
        s = _close_series([100 + i * 0.5 for i in range(60)])
        m, sig, h = macd(s)
        diff = (m - sig) - h
        assert (diff.abs() < 1e-9).all()


class TestVolumeProfile:
    def test_bins_count(self):
        df = pd.DataFrame(
            {
                "O": [100, 101, 102, 103, 104, 105],
                "H": [102, 103, 104, 105, 106, 107],
                "L": [99, 100, 101, 102, 103, 104],
                "C": [101, 102, 103, 104, 105, 106],
                "V": [1000, 2000, 3000, 4000, 5000, 6000],
            }
        )
        bins = volume_profile(df, bins=6)
        assert len(bins) == 6

    def test_pct_sums_to_one(self):
        df = pd.DataFrame(
            {
                "O": [100, 110, 120],
                "H": [105, 115, 125],
                "L": [95, 105, 115],
                "C": [102, 112, 122],
                "V": [1000, 2000, 3000],
            }
        )
        bins = volume_profile(df, bins=4)
        total_pct = sum(b.pct for b in bins)
        assert abs(total_pct - 1.0) < 1e-9

    def test_empty_input(self):
        assert volume_profile(pd.DataFrame()) == []

    def test_zero_range(self):
        df = pd.DataFrame({"H": [100] * 5, "L": [100] * 5, "V": [1] * 5})
        assert volume_profile(df) == []


class TestCompute:
    def test_returns_indicator_bundle(self):
        rng = np.random.default_rng(7)
        n = 60
        close = 100 + rng.normal(0, 1, n).cumsum()
        df = pd.DataFrame(
            {
                "O": close - 0.5,
                "H": close + 1.0,
                "L": close - 1.0,
                "C": close,
                "V": rng.integers(10000, 50000, n),
            }
        )
        b = compute(df)
        assert isinstance(b, IndicatorBundle)
        latest = b.latest()
        assert latest["close"] is not None
        assert latest["ema5"] is not None
