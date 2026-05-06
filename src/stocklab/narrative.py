"""LLM 기반 narrative 생성 — Claude (claude-opus-4-7) 가 시나리오·요약·리스크·결론을 작성.

수치 데이터는 코드(yahoo + indicators)가 결정론적으로 만들고, 자연어 부분만 LLM 에 위임.
JSON Schema 강제 (tool_use) 로 안정적인 구조화 응답을 받는다.
캐시 키는 (ticker, 날짜) 라 동일일자 재실행 시 API 무호출.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date as Date
from pathlib import Path
from typing import Any

import pandas as pd

from stocklab.data.yahoo import StockSnapshot
from stocklab.indicators import IndicatorBundle

CACHE_ROOT = Path.home() / ".cache" / "stocklab" / "narrative"

NARRATIVE_TOOL = {
    "name": "narrative",
    "description": (
        "주식 분석 리포트의 시나리오 3개·핵심 포인트 5개·리스크 3개·최종 결론을 한국어로 작성. "
        "수치는 입력 데이터에 근거하고 임의 추정 금지. 추정은 본문에 '(est.)' 표기."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "scenarios": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["bull", "neutral", "bear"]},
                        "probability": {"type": "integer", "minimum": 0, "maximum": 100},
                        "bullets": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 5, "maxLength": 80},
                            "minItems": 5,
                            "maxItems": 5,
                        },
                        "checks": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 5, "maxLength": 60},
                            "minItems": 3,
                            "maxItems": 3,
                        },
                    },
                    "required": ["kind", "probability", "bullets", "checks"],
                },
            },
            "summary_points": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "maxLength": 18},
                        "body": {"type": "string", "minLength": 10, "maxLength": 90},
                    },
                    "required": ["title", "body"],
                },
            },
            "risks": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "maxLength": 18},
                        "body": {"type": "string", "minLength": 10, "maxLength": 90},
                    },
                    "required": ["title", "body"],
                },
            },
            "verdict": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "enum": [
                            "★ 적극 매수 ★",
                            "★ 분할매수 매력 ★",
                            "⚠ 관망 권장 ⚠",
                            "🚫 비추천 🚫",
                        ],
                    },
                    "sub": {"type": "string", "maxLength": 60},
                },
                "required": ["label", "sub"],
            },
        },
        "required": ["scenarios", "summary_points", "risks", "verdict"],
    },
}

SYSTEM_PROMPT = """당신은 한국·미국 시장을 모두 다루는 시니어 투자 애널리스트다.
사용자가 제공하는 종목 스냅샷(가격·재무·지표)을 기반으로 시나리오 분석과 결론을 한국어로 작성한다.

[작성 규칙]
- 입력 데이터에 명시된 수치만 인용. 임의 추정·예측·환각 금지.
- 추정 또는 외부 추론은 문장 끝에 (est.) 표기.
- 시나리오 3개의 확률 합은 정확히 100.
- 시나리오 본문은 명사형/체언으로 끝내거나 자연스러운 분석 톤. "~할 것이다", "~예상된다" 같은 단정 회피.
- summary_points 의 title 은 18자 이내, body 는 90자 이내. 핵심 키워드만.
- verdict.label 은 정해진 4개 중 하나만 선택.
- 결정 기준:
  · 강세 시나리오 60%+ → "★ 적극 매수 ★"
  · 강세 40~59% → "★ 분할매수 매력 ★"
  · 중립 50%+ → "⚠ 관망 권장 ⚠"
  · 하락 40%+ → "🚫 비추천 🚫"
"""


def _cache_path(ticker: str, day: Date | None = None) -> Path:
    day = day or Date.today()
    return CACHE_ROOT / f"{ticker}-{day:%Y%m%d}.json"


def _build_user_prompt(snap: StockSnapshot, ind: IndicatorBundle, weights: list[str]) -> str:
    latest = ind.latest()

    def _f(v: Any) -> str:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "N/A"
        return f"{v:,.4f}" if isinstance(v, float) else str(v)

    fin = snap.financials
    news_block = "\n".join(
        f"- {n.title}" + (f" (출처: {n.publisher})" if n.publisher else "")
        for n in snap.news[:5]
    ) or "(뉴스 없음)"

    weights_block = ", ".join(weights) if weights else "기본"

    return f"""[종목 스냅샷]
- 티커: {snap.ticker}
- 회사명: {snap.name}
- 자산군: {snap.asset_class}
- 거래소: {snap.exchange or 'N/A'}
- 통화: {snap.currency}
- 현재가: {_f(float(snap.price)) if snap.price else 'N/A'}
- 등락률: {_f(snap.change_pct)}%
- 시가총액: {_f(snap.market_cap)}
- Forward P/E: {_f(snap.pe_forward)}
- P/S (TTM): {_f(snap.ps_ttm)}
- 배당수익률: {_f(snap.div_yield)}
- 52주 고가/저가: {_f(float(snap.week52_high) if snap.week52_high else None)} / {_f(float(snap.week52_low) if snap.week52_low else None)}
- 섹터/산업: {snap.sector or 'N/A'} / {snap.industry or 'N/A'}
- 다음 실적: {snap.next_earnings or 'N/A'}
- 컨센서스: {snap.consensus or 'N/A'}

[재무 (TTM)]
- 매출: {_f(fin.revenue_ttm)} ({snap.currency})
- 순이익: {_f(fin.net_income_ttm)}
- 영업이익률: {_f(fin.operating_margin)} (배수)
- 부채비율 D/E: {_f(fin.debt_to_equity)}
- 현금자산: {_f(fin.cash)}
- 매출 YoY: {_f(fin.revenue_yoy)}
- 순이익 YoY: {_f(fin.net_income_yoy)}

[기술적 지표 — 최근 주봉 기준]
- 종가: {_f(latest.get('close'))}
- EMA 5/20/60/120: {_f(latest.get('ema5'))} / {_f(latest.get('ema20'))} / {_f(latest.get('ema60'))} / {_f(latest.get('ema120'))}
- RSI(14): {_f(latest.get('rsi'))}
- MACD / Signal / Hist: {_f(latest.get('macd'))} / {_f(latest.get('signal'))} / {_f(latest.get('hist'))}

[최근 뉴스]
{news_block}

[옵션 가중]
{weights_block}

위 데이터로 narrative tool 의 schema 에 맞춰 작성하라.
"""


def generate(
    snap: StockSnapshot,
    ind: IndicatorBundle,
    weights: list[str] | None = None,
    use_cache: bool = True,
) -> dict[str, Any] | None:
    """Claude 호출로 narrative 생성. API 키 없거나 실패 시 None 반환."""
    weights = weights or []

    cache_p = _cache_path(snap.ticker)
    if use_cache and cache_p.exists():
        try:
            return json.loads(cache_p.read_text(encoding="utf-8"))
        except Exception:
            pass

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = _build_user_prompt(snap, ind, weights)
    try:
        resp = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            tools=[NARRATIVE_TOOL],
            tool_choice={"type": "tool", "name": "narrative"},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as e:
        print(f"[narrative] Claude 호출 실패: {e}")
        return None

    result: dict[str, Any] | None = None
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "narrative":
            result = dict(block.input)
            break

    if result is None:
        return None

    # 결과 보강: scenario kind 별로 emoji / title 채워서 stock.py 가 받아쓸 수 있게.
    kind_meta = {
        "bull": ("🚀", "강세 시나리오"),
        "neutral": ("📊", "중립 시나리오"),
        "bear": ("🐻", "하락 시나리오"),
    }
    for s in result.get("scenarios", []):
        emoji, title = kind_meta.get(s["kind"], ("", s["kind"]))
        s.setdefault("emoji", emoji)
        s.setdefault("title", title)
        # target_range 는 코드가 가격 기반으로 채움 — Claude 가 임의 추정 금지
        s.setdefault("target_range", "")

    # 번호 부여
    for i, p in enumerate(result.get("summary_points", []), 1):
        p["num"] = f"{i:02d}"
    for i, r in enumerate(result.get("risks", []), 1):
        r["num"] = f"R{i}"

    # 캐시 저장
    try:
        cache_p.parent.mkdir(parents=True, exist_ok=True)
        cache_p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return result


def merge_target_ranges(narrative: dict[str, Any], code_scenarios: list[Any]) -> dict[str, Any]:
    """Claude 가 만든 시나리오에 코드가 계산한 가격 범위(target_range)를 주입."""
    code_by_kind = {s.kind: s for s in code_scenarios}
    for s in narrative.get("scenarios", []):
        code = code_by_kind.get(s["kind"])
        if code:
            s["target_range"] = code.target_range
    return narrative
