"""관심종목 관리 명령어 핸들러."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot import storage


async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/관심목록 또는 /list — 관심종목 출력."""
    if not update.message or not update.effective_user:
        return
    items = storage.get_watchlist(update.effective_user.id)
    if not items:
        await update.message.reply_text("📋 관심종목 없음.\n`/관심추가 NVDA` 로 추가하세요.")
        return
    body = "\n".join(f"  • {t}" for t in items)
    await update.message.reply_text(f"📋 *관심종목 ({len(items)}개)*\n{body}", parse_mode="Markdown")


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/관심추가 TICKER."""
    if not update.message or not update.effective_user or not context.args:
        await update.message.reply_text("사용법: `/관심추가 NVDA`", parse_mode="Markdown")
        return
    ticker = context.args[0]
    items = storage.add_to_watchlist(update.effective_user.id, ticker)
    await update.message.reply_text(f"✅ {ticker.upper()} 추가됨. 현재 {len(items)}개.")


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/관심제거 TICKER."""
    if not update.message or not update.effective_user or not context.args:
        await update.message.reply_text("사용법: `/관심제거 NVDA`", parse_mode="Markdown")
        return
    ticker = context.args[0]
    items = storage.remove_from_watchlist(update.effective_user.id, ticker)
    await update.message.reply_text(f"🗑 {ticker.upper()} 제거됨. 현재 {len(items)}개.")
