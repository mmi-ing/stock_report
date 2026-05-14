"""모드 A/B/C 자동 분기.

README §1 의 4 단계 우선순위를 코드로:
    1) "vs" / "비교" → Mode C
    2) 정규식 티커 → Mode A
    3) 한국 회사명 / ETF 사전 → Mode A
    4) 테마 키워드 사전 → Mode B
    5) 모호 → AmbiguousResult
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from stocklab.config import ETF_TICKERS, KR_NAME_TO_TICKER, WEIGHT_PRESETS
from stocklab.data import theme_pool

Mode = Literal["A", "B", "C", "ambiguous"]

# README §1 [2순위] 정규식 패턴
RE_US_TICKER = re.compile(r"^[A-Z]{1,5}$")
RE_KR_CODE = re.compile(r"^\d{6}$")
RE_KR_SUFFIX = re.compile(r"^\d{6}\.(KS|KQ)$", re.IGNORECASE)
RE_CRYPTO = re.compile(r"^[A-Z0-9]{2,6}-USD$", re.IGNORECASE)


@dataclass
class RouteSpec:
    mode: Mode
    raw_input: str
    # Mode A
    ticker: str | None = None
    asset_class: Literal["us_stock", "kr_stock", "etf", "crypto"] | None = None
    display_name: str | None = None
    # Mode B
    theme: str | None = None
    candidates: list[str] = field(default_factory=list)
    # Mode C
    left: str | None = None
    right: str | None = None
    # 옵션
    weights: list[str] = field(default_factory=list)
    # 모호 시 후보
    ambiguous_options: list[str] = field(default_factory=list)


def _classify_ticker(ticker: str) -> tuple[str, str]:
    """티커 정규화 + 자산군 분류. Returns (normalized, asset_class)."""
    t = ticker.strip()
    if RE_CRYPTO.match(t):
        return t.upper(), "crypto"
    if RE_KR_SUFFIX.match(t):
        return t.upper(), "kr_stock"
    if RE_KR_CODE.match(t):
        # 접미사 없는 6자리는 일단 .KS 로 정규화 (yahoo 폴백 시 .KQ 도 시도)
        return f"{t}.KS", "kr_stock"
    if RE_US_TICKER.match(t):
        if t in ETF_TICKERS:
            return t, "etf"
        return t, "us_stock"
    return t, "us_stock"  # 미상은 일단 미국 주식 가정


def _extract_weights(text: str) -> tuple[str, list[str]]:
    """입력에서 옵션 키워드 (단기·심층·공격적 등) 를 분리해 weights 로 추출.

    "NVDA 단기 심층" → ("NVDA", ["short", "deep"])
    """
    tokens = text.split()
    weights: list[str] = []
    rest: list[str] = []
    for tok in tokens:
        if tok in WEIGHT_PRESETS:
            weights.append(WEIGHT_PRESETS[tok])
        else:
            rest.append(tok)
    return " ".join(rest).strip(), weights


def _strip_b_keywords(text: str) -> str:
    """'추천', '유망주', '수혜주' 같은 모드 B 트리거어를 제거해 테마 키 매칭을 돕는다."""
    for kw in ("추천", "유망주", "수혜주"):
        text = text.replace(kw, " ")
    return " ".join(text.split())


def parse(raw: str) -> RouteSpec:
    """README §1 우선순위로 모드를 결정한다."""
    if not raw or not raw.strip():
        return RouteSpec(mode="ambiguous", raw_input=raw, ambiguous_options=["empty"])

    text = raw.strip()
    text_no_weights, weights = _extract_weights(text)

    # [1순위] 비교 모드
    lowered = text_no_weights.lower()
    if " vs " in f" {lowered} " or " vs. " in f" {lowered} " or "비교" in text_no_weights:
        # vs 토큰 분리 (대소문자/공백/마침표 허용)
        parts = re.split(r"\s+vs\.?\s+|\s*비교\s*", text_no_weights, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 2:
            return RouteSpec(
                mode="C",
                raw_input=raw,
                left=parts[0],
                right=parts[1],
                weights=weights,
            )

    tokens = text_no_weights.split()

    # [2순위] 단일 토큰 + 명시적 티커 패턴 → Mode A (대소문자 무관)
    if len(tokens) == 1:
        candidate = tokens[0].upper()
        if (
            RE_CRYPTO.match(candidate)
            or RE_KR_SUFFIX.match(candidate)
            or RE_KR_CODE.match(candidate)
            or RE_US_TICKER.match(candidate)
        ):
            ticker, klass = _classify_ticker(candidate)
            return RouteSpec(
                mode="A",
                raw_input=raw,
                ticker=ticker,
                asset_class=klass,  # type: ignore[arg-type]
                display_name=candidate,
                weights=weights,
            )

    # [3순위] 한국 회사명 사전 — 정확히 포함되는 경우 우선 (긴 이름 먼저)
    for name in sorted(KR_NAME_TO_TICKER.keys(), key=len, reverse=True):
        if name in text_no_weights:
            return RouteSpec(
                mode="A",
                raw_input=raw,
                ticker=KR_NAME_TO_TICKER[name],
                asset_class="kr_stock",
                display_name=name,
                weights=weights,
            )

    # [3.5순위] 부분 이름 매칭 — "하이닉스" → "SK하이닉스" 등 포함 검색
    partial = [(n, t) for n, t in KR_NAME_TO_TICKER.items() if text_no_weights in n]
    if len(partial) == 1:
        name, ticker_val = partial[0]
        return RouteSpec(
            mode="A",
            raw_input=raw,
            ticker=ticker_val,
            asset_class="kr_stock",
            display_name=name,
            weights=weights,
        )
    if len(partial) > 1:
        return RouteSpec(
            mode="ambiguous",
            raw_input=raw,
            weights=weights,
            ambiguous_options=[f"{n} ({t})" for n, t in partial],
        )

    # [4순위] 테마 키워드 — 원문 / "수혜주" 등 제거 후 두 번 시도
    found = theme_pool.find_theme(text_no_weights)
    if found is None:
        found = theme_pool.find_theme(_strip_b_keywords(text_no_weights))
    if found is not None:
        theme_key, candidates = found
        return RouteSpec(
            mode="B",
            raw_input=raw,
            theme=theme_key,
            candidates=candidates,
            weights=weights,
        )

    # [5순위] 모호 — 가장 가까운 후보 몇 개 제안
    return RouteSpec(
        mode="ambiguous",
        raw_input=raw,
        weights=weights,
        ambiguous_options=[
            "개별 종목 분석을 원하시면 정확한 티커(NVDA, 005930)나 회사명(삼성전자)을 입력하세요.",
            "테마 발굴을 원하시면 '소부장 추천', 'AI 반도체' 같은 키워드를 입력하세요.",
        ],
    )
