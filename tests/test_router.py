"""router.parse 단위 테스트 — README §1 우선순위 검증."""
from __future__ import annotations

import pytest

from stocklab.router import parse


class TestModeC비교:
    def test_vs_lowercase(self):
        spec = parse("NVDA vs AMD")
        assert spec.mode == "C"
        assert spec.left == "NVDA"
        assert spec.right == "AMD"

    def test_vs_dot(self):
        spec = parse("AAPL vs. MSFT")
        assert spec.mode == "C"
        assert spec.left == "AAPL"
        assert spec.right == "MSFT"

    def test_korean_비교(self):
        spec = parse("삼성전자 비교 SK하이닉스")
        assert spec.mode == "C"

    def test_uppercase_VS(self):
        spec = parse("NVDA VS AMD")
        assert spec.mode == "C"


class TestModeA개별:
    def test_us_ticker(self):
        spec = parse("NVDA")
        assert spec.mode == "A"
        assert spec.ticker == "NVDA"
        assert spec.asset_class == "us_stock"

    def test_etf(self):
        spec = parse("QQQ")
        assert spec.mode == "A"
        assert spec.asset_class == "etf"

    def test_crypto(self):
        spec = parse("BTC-USD")
        assert spec.mode == "A"
        assert spec.asset_class == "crypto"
        assert spec.ticker == "BTC-USD"

    def test_kr_code_normalizes_to_KS(self):
        spec = parse("005930")
        assert spec.mode == "A"
        assert spec.asset_class == "kr_stock"
        assert spec.ticker == "005930.KS"

    def test_kr_code_with_suffix(self):
        spec = parse("042700.KQ")
        assert spec.mode == "A"
        assert spec.asset_class == "kr_stock"
        assert spec.ticker == "042700.KQ"

    def test_korean_company_name(self):
        spec = parse("삼성전자")
        assert spec.mode == "A"
        assert spec.ticker == "005930.KS"
        assert spec.display_name == "삼성전자"

    def test_korean_kosdaq_company(self):
        spec = parse("한미반도체")
        assert spec.mode == "A"
        assert spec.ticker == "042700.KQ"


class TestModeB발굴:
    def test_kr_theme_with_추천(self):
        spec = parse("소부장 추천")
        assert spec.mode == "B"
        assert spec.theme == "소부장"
        assert "042700.KQ" in spec.candidates

    def test_us_theme(self):
        spec = parse("AI 반도체")
        assert spec.mode == "B"
        assert spec.theme == "AI 반도체"
        assert "NVDA" in spec.candidates

    def test_macro_theme(self):
        spec = parse("금리 인하 수혜주")
        assert spec.mode == "B"
        assert spec.theme == "금리 인하 수혜주"

    def test_longer_match_priority(self):
        # "AI 반도체" 가 "반도체" 보다 먼저 매칭돼야 함
        spec = parse("AI 반도체 추천")
        assert spec.theme == "AI 반도체"


class TestWeights옵션:
    def test_short_weight(self):
        spec = parse("NVDA 단기")
        assert spec.mode == "A"
        assert spec.ticker == "NVDA"
        assert "short" in spec.weights

    def test_deep_weight(self):
        spec = parse("NVDA 심층")
        assert spec.mode == "A"
        assert "deep" in spec.weights

    def test_aggressive_for_theme(self):
        spec = parse("AI 반도체 공격적")
        assert spec.mode == "B"
        assert "aggressive" in spec.weights

    def test_multiple_weights(self):
        spec = parse("NVDA 단기 심층")
        assert spec.mode == "A"
        assert "short" in spec.weights
        assert "deep" in spec.weights


class TestAmbiguous:
    def test_empty(self):
        spec = parse("")
        assert spec.mode == "ambiguous"

    def test_unknown_word(self):
        spec = parse("뭔가알수없는단어")
        assert spec.mode == "ambiguous"


class TestC비교_with_weights:
    def test_compare_with_weight(self):
        spec = parse("NVDA vs AMD 단기")
        assert spec.mode == "C"
        assert "short" in spec.weights
