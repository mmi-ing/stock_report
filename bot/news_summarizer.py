"""Claude API로 뉴스 한국어 요약.

ANTHROPIC_API_KEY 없으면 원문 제목 리스트로 폴백.
"""
from __future__ import annotations

import os

from bot.news_fetcher import NewsItem


def summarize(ticker: str | None, items: list[NewsItem]) -> str:
    """뉴스 목록 → 한국어 요약 텍스트 (Telegram 마크다운).

    API 키 없거나 호출 실패 시 원문 제목 리스트 반환.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not items:
        return _fallback(ticker, items)

    try:
        return _llm_summary(ticker, items, api_key)
    except Exception as e:
        print(f"[news_summarizer] LLM 실패, 폴백: {e}")
        return _fallback(ticker, items)


def _llm_summary(ticker: str | None, items: list[NewsItem], api_key: str) -> str:
    import anthropic

    label = ticker if ticker and ticker != "MARKET" else "시장 전체"

    news_block = "\n".join(
        f"{i+1}. 제목: {it.title}\n   내용: {it.summary or '(없음)'}\n   시간: {it.published}"
        for i, it in enumerate(items)
    )

    prompt = f"""다음은 {label} 관련 최신 뉴스입니다. 투자자 관점에서 핵심을 한국어로 요약해 주세요.

{news_block}

형식:
- 각 뉴스를 1~2문장으로 요약 (번호 유지)
- 마지막 줄에 ★ 전체 한 줄 시황 (예: "전반적으로 강세 / 불확실성 높음 / 주목할 이벤트 없음" 등)
- 이모지 사용 가능, 전문 용어는 간결하게
- 원문 링크나 영어 그대로 쓰지 말 것"""

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    summary_text = resp.content[0].text.strip()

    header = f"📰 *{label} 뉴스 요약*"
    # 원문 링크 모음 (접기)
    link_lines = "\n".join(
        f"  {i+1}. [{_short(it.title)}]({it.url})" for i, it in enumerate(items)
    )
    return f"{header}\n\n{summary_text}\n\n_원문 링크_\n{link_lines}"


def _fallback(ticker: str | None, items: list[NewsItem]) -> str:
    """API 없을 때: 원문 제목 + 링크."""
    from bot.news_fetcher import format_news_message
    return format_news_message(ticker, items)


def _short(title: str, max_len: int = 40) -> str:
    return title[:max_len] + "…" if len(title) > max_len else title
