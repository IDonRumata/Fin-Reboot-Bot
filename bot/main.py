"""Main entry point — assembles bot, registers routers, starts polling."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.core.bot_instance import create_bot, create_dispatcher
from bot.core.config import settings
from bot.database.engine import engine
from bot.database.models import Base
from bot.middlewares.antiflood import AntiFloodMiddleware
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.logging_mw import LoggingMiddleware

# Handler routers
from bot.handlers import (
    start,
    menu,
    buy,
    progress,
    day_done,
    continue_block,
    keywords,
    admin,
    fallback,
    quiz,
)
from bot.workers.day_scheduler import check_and_send_next_day
from bot.workers.reminders import check_and_send_reminders
from bot.workers.quiz_followup import check_and_send_quiz_followups
from bot.workers.backup import create_and_send_backup
from bot.services.webhook import create_webhook_app

logger = logging.getLogger(__name__)


async def on_startup(bot, **_kwargs) -> None:
    """Called once when the bot starts."""
    # Create tables (in production use Alembic migrations instead)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured.")

    # Always sync content from CSV on startup
    from bot.database.engine import async_session
    from bot.handlers.admin import _import_csv
    from pathlib import Path

    csv_path = Path(__file__).parent.parent / "data" / "content_blocks.csv"
    if csv_path.exists():
        async with async_session() as session:
            imported = await _import_csv(session, csv_path)
            logger.info("Auto-sync: loaded %d content blocks from CSV.", imported)
    else:
        logger.warning("No CSV file found at %s — skipping auto-sync.", csv_path)


async def main() -> None:
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    bot = create_bot()
    dp = create_dispatcher()

    # Register middlewares (order matters: outer → inner)
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.message.middleware(AntiFloodMiddleware(rate_limit=0.5))
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    # Register routers (order matters: first match wins)
    dp.include_router(admin.router)       # Admin first (commands with checks)
    dp.include_router(quiz.router)        # Quiz FSM (before start!)
    dp.include_router(start.router)       # /start
    dp.include_router(menu.router)        # /menu, about, support
    dp.include_router(buy.router)         # buy, oferta, accept, payment
    dp.include_router(progress.router)    # /progress
    dp.include_router(day_done.router)    # day_X_done
    dp.include_router(continue_block.router)  # cont_dX_bY
    dp.include_router(keywords.router)    # АРЕНДА, РОБОТ
    dp.include_router(fallback.router)    # Catch-all (LAST!)

    # Startup hook
    dp.startup.register(on_startup)

    # Background schedulers
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_and_send_next_day,
        "interval",
        minutes=settings.day_scheduler_interval_minutes,
        args=[bot],
        id="day_scheduler",
        replace_existing=True,
    )
    scheduler.add_job(
        check_and_send_reminders,
        "interval",
        hours=settings.reminder_interval_hours,
        args=[bot],
        id="reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        check_and_send_quiz_followups,
        "interval",
        minutes=15,
        args=[bot],
        id="quiz_followup",
        replace_existing=True,
    )
    scheduler.add_job(
        create_and_send_backup,
        "cron",
        hour=3,
        minute=0,
        args=[bot],
        id="daily_backup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Schedulers started: day_scheduler every %d min, reminders every %d hours, quiz_followup every 15 min.",
        settings.day_scheduler_interval_minutes,
        settings.reminder_interval_hours,
    )

    # Start webhook server for bePaid notifications
    webhook_app = create_webhook_app(bot)
    runner = web.AppRunner(webhook_app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        host=settings.webhook_host,
        port=settings.webhook_port,
    )
    await site.start()
    logger.info(
        "Webhook server started on %s:%s",
        settings.webhook_host,
        settings.webhook_port,
    )

    # Start polling
    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await runner.cleanup()
        await engine.dispose()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
