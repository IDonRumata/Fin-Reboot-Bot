"""Reminders — send 48h reminders for incomplete tasks.

Replaces Fin_Reboot_Reminders n8n workflow.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database.engine import async_session
from bot.database import repositories as repo

logger = logging.getLogger(__name__)


async def check_and_send_reminders(bot: Bot) -> None:
    """Background job: find users needing 48h reminders and send them."""
    logger.info("Reminders: checking for users needing reminders...")

    async with async_session() as session:
        users_to_remind = await repo.get_users_needing_reminder(session)

        if not users_to_remind:
            logger.info("Reminders: no users need reminders right now.")
            return

        logger.info("Reminders: found %d users to remind.", len(users_to_remind))

        for entry in users_to_remind:
            user = entry["user"]
            day = entry["day"]
            title = entry["title"]

            text = (
                f"👋 Привет!\n\n"
                f"Ты на <b>Дне {day}</b> курса «Графин» – {title}.\n\n"
                f"Ты ещё не отметил(а) задание как выполненное. Нужна помощь?\n\n"
                f"Когда будешь готов(а) – нажми кнопку ниже:"
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Задание выполнено!",
                            callback_data=f"day_{day}_done",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🆘 Нужна помощь",
                            callback_data="support",
                        )
                    ],
                ]
            )

            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=text,
                    reply_markup=keyboard,
                )
                await repo.mark_reminder_sent(session, user.id, day)
                logger.info("Reminder sent to user %s for day %d", user.telegram_id, day)
            except Exception as exc:
                logger.error(
                    "Failed to send reminder to user %s: %s",
                    user.telegram_id,
                    exc,
                )
