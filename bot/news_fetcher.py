"""뉴스 fetcher — Yahoo Finance RSS (기본) + yfinance (fallback).

외부 API 키 불필요. 완전 무료.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


@dataclass
class NewsItem:
    id: str        # URL MD5 앞 16자
    ticker: str
    title: str
    summary: str
    url: str
    published: str  # "MM/DD HH:MM" 형식


def _uid(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _parse_pubdate(raw: str) -> str:
    """RFC 2822 또는 ISO 8601 날짜 → "MM/DD HH:MM" 변환."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        return dt.astimezone(timezone.utc).strftime("%m/%d %H:%M")
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%m/%d %H:%M")
    except Exception:
        return raw[:10]


def _strip_cdata(s: str) -> str:
    m = re.search(r"<!\[CDATA\[(.*?)]]>", s, re.DOTALL)
    return m.group(1).strip() if m else s.strip()


def _parse_rss_xml(xml_text: str, ticker: str) -> list[NewsItem]:
    """ElementTree 기반 RSS 파싱. CDATA 포함 Yahoo RSS 대응."""
    # ElementTree는 CDATA를 일반 텍스트로 읽으므로 먼저 해제
    text = re.sub(r"<!\[CDATA\[", "", xml_text)
    text = re.sub(r"]]>", "", text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or item.findtext("guid") or "").strip()
        summary = (item.findtext("description") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()

        if not title or not url:
            continue

        # HTML 태그 제거
        summary = re.sub(r"<[^>]+>", "", summary)[:300]

        items.append(NewsItem(
            id=_uid(url),
            ticker=ticker,
            title=title,
            summary=summary,
            url=url,
            published=_parse_pubdate(pub) if pub else "",
        ))
    return items


_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; stocklab-bot/1.0)"}


def fetch_ticker_news(ticker: str, max_items: int = 7) -> list[NewsItem]:
    """Yahoo Finance RSS → yfinance fallback 순서로 뉴스 가져오기."""
    # 1) Yahoo Finance RSS
    url = f"https://finance.yahoo.com/rss/headline?s={ticker}"
    try:
        resp = httpx.get(url, timeout=12, headers=_HEADERS, follow_redirects=True)
        if resp.status_code == 200 and "<item>" in resp.text:
            items = _parse_rss_xml(resp.text, ticker)
            if items:
                return items[:max_items]
    except Exception:
        pass

    # 2) yfinance fallback
    return _yf_news(ticker, max_items)


def _yf_news(ticker: str, max_items: int = 7) -> list[NewsItem]:
    try:
        import yfinance as yf
        raw = yf.Ticker(ticker).news or []
        items = []
        for n in raw[:max_items]:
            content = n.get("content", {})
            title = content.get("title") or n.get("title", "")
            url = (
                content.get("canonicalUrl", {}).get("url")
                or n.get("link", "")
            )
            summary = (content.get("summary") or "")[:300]
            pub_raw = content.get("pubDate") or ""
            published = _parse_pubdate(pub_raw) if pub_raw else ""
            if title and url:
                items.append(NewsItem(
                    id=_uid(url), ticker=ticker, title=title,
                    summary=summary, url=url, published=published,
                ))
        return items
    except Exception:
        return []


def fetch_market_news(max_items: int = 8) -> list[NewsItem]:
    """Yahoo Finance 전체 시장 RSS (티커 무관 주요 뉴스)."""
    url = "https://finance.yahoo.com/news/rssindex"
    try:
        resp = httpx.get(url, timeout=12, headers=_HEADERS, follow_redirects=True)
        if resp.status_code == 200 and "<item>" in resp.text:
            return _parse_rss_xml(resp.text, "MARKET")[:max_items]
    except Exception:
        pass
    return []


def format_news_message(ticker: str | None, items: list[NewsItem]) -> str:
    """텔레그램 마크다운 메시지 포맷."""
    if not items:
        return "뉴스를 가져오지 못했어요. 잠시 후 다시 시도해 주세요."

    header = f"📰 *{ticker} 최신 뉴스*" if ticker else "📰 *시장 주요 뉴스*"
    lines = [header, ""]
    for it in items:
        pub = f"  _({it.published})_" if it.published else ""
        # Markdown 특수문자 최소 이스케이프
        title = it.title.replace("[", "\\[").replace("]", "\\]")
        lines.append(f"• [{title}]({it.url}){pub}")
    return "\n".join(lines)
