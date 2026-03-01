"""Day Scheduler – checks every N minutes for users ready for the next day.

Replaces Fin_Reboot_Day_Scheduler_v2 n8n workflow.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from bot.core.config import settings
from bot.database.engine import async_session
from bot.database import repositories as repo
from bot.services.content_sender import send_full_day

logger = logging.getLogger(__name__)

PAYMENT_CONFIRMED_TEXT = (
    "━━━━━━━━━━━━━━━━━━━\n"
    "✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n"
    "━━━━━━━━━━━━━━━━━━━\n\n"
    "Спасибо за покупку программы «Финансовая перезагрузка»! 🎉\n\n"
    "👉 Присоединяйтесь к нашему чату участников "
    "для общения и обратной связи:\n"
    f"{settings.participants_chat_url}\n\n"
    "📚 Первый день программы начнётся через несколько секунд!"
)


async def check_and_send_next_day(bot: Bot) -> None:
    """Background job: find users who need the next day and send it."""
    logger.info("Day Scheduler: checking for users needing next day...")

    async with async_session() as session:
        users_to_send = await repo.get_users_needing_next_day(session)

        if not users_to_send:
            logger.info("Day Scheduler: no users need next day right now.")
            return

        logger.info("Day Scheduler: found %d users to send.", len(users_to_send))

        for entry in users_to_send:
            user = entry["user"]
            day = entry["day"]
            reason = entry["reason"]

            logger.info(
                "Sending day %d to user %s (reason: %s)",
                day,
                user.telegram_id,
                reason,
            )

            try:
                # Send payment confirmation message before Day 1
                if day == 1 and reason == "paid_day1_autostart":
                    await bot.send_message(
                        user.telegram_id,
                        PAYMENT_CONFIRMED_TEXT,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                    await asyncio.sleep(3)

                await send_full_day(
                    bot=bot,
                    session=session,
                    telegram_id=user.telegram_id,
                    user_id=user.id,
                    day=day,
                )
            except Exception as exc:
                logger.error(
                    "Failed to send day %d to user %s: %s",
                    day,
                    user.telegram_id,
                    exc,
                )
