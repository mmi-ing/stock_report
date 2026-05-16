"""미장 프리뷰 (저녁 20:00 KST) — 오늘 밤 미장 주목 포인트.

GitHub Actions cron 또는 봇 내부 JobQueue 에서 호출.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from stocklab.data import yahoo
from bot import storage


def _fetch_index(ticker: str) -> tuple[str, float | None, float | None]:
    """지수/티커 → (이름, 가격, 변동률%) 반환. 실패시 None."""
    try:
        snap = yahoo.fetch(ticker, "us_stock")
        price = float(snap.price) if snap.price else None
        return (ticker, price, snap.change_pct)
    except Exception:
        return (ticker, None, None)


def build_premarket_brief() -> str:
    """미장 프리뷰 텍스트 (마크다운)."""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"🌃 *미장 프리뷰 · {today}*", ""]

    # 1) 어제 미장 + 매크로
    lines.append("*어제 미장*")
    for ticker, label in [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^DJI", "Dow"), ("^VIX", "VIX"), ("KRW=X", "USD/KRW")]:
        _, price, chg = _fetch_index(ticker)
        if price is None:
            lines.append(f"  • {label}: N/A")
            continue
        sign = "🟢" if (chg or 0) >= 0 else "🔴"
        chg_str = f"{chg:+.2f}%" if chg is not None else "-"
        lines.append(f"  {sign} {label}: {price:,.2f} ({chg_str})")

    return "\n".join(lines)


def build_postmarket_summary() -> str:
    """미장 마감 요약 (아침 07:30 KST 발송용)."""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"☀️ *미장 마감 요약 · {today}*", ""]
    for ticker, label in [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^DJI", "Dow"), ("^VIX", "VIX"), ("KRW=X", "USD/KRW")]:
        _, price, chg = _fetch_index(ticker)
        if price is None:
            lines.append(f"  • {label}: N/A")
            continue
        sign = "🟢" if (chg or 0) >= 0 else "🔴"
        chg_str = f"{chg:+.2f}%" if chg is not None else "-"
        lines.append(f"  {sign} {label}: {price:,.2f} ({chg_str})")
    return "\n".join(lines)


def build_user_watchlist_brief(user_id: int) -> str | None:
    """특정 사용자의 관심종목 변동 요약."""
    items = storage.get_watchlist(user_id)
    if not items:
        return None
    lines = ["📋 *관심종목 변동*"]
    for ticker in items:
        _, price, chg = _fetch_index(ticker)
        if price is None:
            lines.append(f"  • {ticker}: N/A")
            continue
        sign = "🟢" if (chg or 0) >= 0 else "🔴"
        chg_str = f"{chg:+.2f}%" if chg is not None else "-"
        lines.append(f"  {sign} {ticker}: ${price:,.2f} ({chg_str})")
    return "\n".join(lines)


async def broadcast(bot, brief_fn) -> None:
    """관심종목 등록한 모든 사용자에게 발송."""
    users = storage.all_users_with_watchlist()
    common = brief_fn()
    for user_id_str in users.keys():
        try:
            user_id = int(user_id_str)
            personal = build_user_watchlist_brief(user_id)
            text = common + (f"\n\n{personal}" if personal else "")
            await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        except Exception as e:
            print(f"broadcast fail {user_id_str}: {e}")
