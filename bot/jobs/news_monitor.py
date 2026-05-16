"""관심종목 뉴스 모니터링 (2시간마다).

새 기사가 있으면 해당 사용자에게만 텔레그램 알림 발송.
중복 전송은 SQLite(news_db)로 방지.
"""
from __future__ import annotations

import asyncio

from telegram.ext import ContextTypes

from bot import news_db, news_fetcher, storage


async def job_news_monitor(context: ContextTypes.DEFAULT_TYPE) -> None:
    """모든 관심종목 새 뉴스 체크 & 푸시."""
    news_db.cleanup_old(days=7)
    users = storage.all_users_with_watchlist()

    for user_id_str, tickers in users.items():
        user_id = int(user_id_str)
        for ticker in tickers:
            try:
                items = await asyncio.to_thread(
                    news_fetcher.fetch_ticker_news, ticker, 5
                )
                new_items = [it for it in items if not news_db.is_sent(it.id)]
                if not new_items:
                    continue

                msg = news_fetcher.format_news_message(ticker, new_items[:3])
                msg = "🔔 " + msg  # 알림 강조

                await context.bot.send_message(
                    chat_id=user_id,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
                for it in new_items:
                    news_db.mark_sent(it.id, ticker, it.title)

            except Exception as e:
                print(f"[news_monitor] {ticker} → {user_id_str}: {e}")
