"""/news [TICKER] — 최신 뉴스 즉시 조회."""
from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from bot import news_fetcher


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    ticker = (context.args[0].upper() if context.args else "").strip()

    if ticker:
        await update.message.reply_text(f"📰 {ticker} 뉴스 불러오는 중…")
        items = await asyncio.to_thread(news_fetcher.fetch_ticker_news, ticker, 7)
        msg = news_fetcher.format_news_message(ticker, items)
    else:
        await update.message.reply_text("📰 시장 뉴스 불러오는 중…")
        items = await asyncio.to_thread(news_fetcher.fetch_market_news, 8)
        msg = news_fetcher.format_news_message(None, items)

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
