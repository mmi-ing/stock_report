"""Stock Lab 텔레그램 봇 메인.

환경변수:
- TELEGRAM_BOT_TOKEN: @BotFather 에서 발급
- ANTHROPIC_API_KEY: (선택) narrative LLM
"""
from __future__ import annotations

import logging
import os
from datetime import time as dtime

import pytz
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.handlers import ticker as h_ticker
from bot.handlers import watchlist as h_watchlist
from bot.jobs.premarket import broadcast, build_postmarket_summary, build_premarket_brief

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)

HELP = """\
*Stock Lab 봇 사용법*

🔍 검색
  • `NVDA` / `엔비디아` / `005930` / `삼성전자`
  • `AI 반도체 추천` (테마)
  • `NVDA vs AMD` (비교)

📋 관심종목
  • `/관심추가 NVDA`
  • `/관심제거 NVDA`
  • `/관심목록`

⏰ 자동 알림
  • 07:30 KST · 미장 마감 요약 + 내 관심종목 변동
  • 20:00 KST · 미장 프리뷰 + 내 관심종목

✉️ 그냥 종목/테마 이름 보내면 자동 분석.
"""


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP, parse_mode="Markdown")


async def job_premarket(context: ContextTypes.DEFAULT_TYPE) -> None:
    await broadcast(context.bot, build_premarket_brief)


async def job_postmarket(context: ContextTypes.DEFAULT_TYPE) -> None:
    await broadcast(context.bot, build_postmarket_summary)


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN 환경변수 필요")

    app = Application.builder().token(token).build()

    # 명령어
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler(["관심목록", "list", "watchlist"], h_watchlist.cmd_watchlist))
    app.add_handler(CommandHandler(["관심추가", "add"], h_watchlist.cmd_add))
    app.add_handler(CommandHandler(["관심제거", "remove", "rm"], h_watchlist.cmd_remove))

    # 자유 텍스트 → 종목/테마 분석
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, h_ticker.handle_query))

    # 스케줄: KST 기준
    if app.job_queue:
        kst = pytz.timezone("Asia/Seoul")
        app.job_queue.run_daily(job_postmarket, time=dtime(hour=7, minute=30, tzinfo=kst))
        app.job_queue.run_daily(job_premarket, time=dtime(hour=20, minute=0, tzinfo=kst))

    print("🤖 Stock Lab 봇 시작...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
