"""Quiz follow-up worker - sends 3 drip messages to quiz completers who haven't purchased.

Schedule: every 15 minutes via APScheduler.
Chain:
  step 0 → +1 hour  → message 1 (free fact + CTA)
  step 1 → +24 hours → message 2 (Marina's story + CTA)
  step 2 → +72 hours → message 3 (final push, open question)
  step 3 → done (no more messages)

Stops if user purchased (payment_status == paid).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database import repositories as repo
from bot.database.engine import async_session

logger = logging.getLogger(__name__)

# ──────────────────── Followup messages ───────────────────────

FOLLOWUP_MESSAGES = {
    1: {
        "delay_hours": 1,
        "text": (
            "🎁 <b>Кстати, забыли сказать!</b>\n\n"
            "Первые 50 участников получают бонус:\n\n"
            "📋 <b>Чек-лист «Первая инвестиция за 15 минут»</b>\n\n"
            "7 конкретных шагов — от скачивания приложения "
            "до первой покупки ETF. Без воды, без теории.\n\n"
            "Чек-лист идёт бонусом к «Графину» — "
            "отправим сразу после оплаты.\n\n"
            "💰 Стоимость: <b>45 BYN</b>"
        ),
    },
    2: {
        "delay_hours": 6,
        "text": (
            "👋 <b>Привет!</b>\n\n"
            "Это Марина и Андрей.\n\n"
            "Видели, что ты прошёл(а) квиз — и результат "
            "показал, что потенциал есть.\n\n"
            "Знаешь, что самое сложное в инвестициях? "
            "Не выбрать акции. Не разобраться в графиках.\n\n"
            "Самое сложное — <b>начать</b>.\n\n"
            "Мы оба через это прошли. Марина откладывала "
            "решение 2 года. Андрей начал прямо в рейсе, "
            "с телефона, с $50.\n\n"
            "«Графин» — это 5 дней, после которых ты точно начнёшь. "
            "Потому что мы проведём тебя за руку.\n\n"
            "💰 <b>45 BYN</b> — один раз, доступ навсегда."
        ),
    },
    3: {
        "delay_hours": 72,
        "text": (
            "👋 <b>Последнее сообщение от нас</b>\n\n"
            "Мы не будем надоедать — это последнее напоминание.\n\n"
            "Просто один вопрос: что тебя останавливает?\n\n"
            "Если дело в цене — 45 BYN. "
            "Это один поход в кафе.\n\n"
            "Если дело в сомнениях — мы понимаем. "
            "Но 90% людей так и не начинают инвестировать "
            "именно из-за сомнений. А потом жалеют.\n\n"
            "Шпаргалка по налогам — уже твоя. "
            "«Графин» — когда будешь готов(а) 🙂\n\n"
            "Подпишись на нас:\n"
            "Марина: "
            '<a href="https://tiktok.com/@dementjeva17">TikTok</a> · '
            '<a href="https://instagram.com/marina_dementjeva">Instagram</a>\n'
            "Андрей: "
            '<a href="https://tiktok.com/@krononchill">TikTok</a> · '
            '<a href="https://instagram.com/krononchill">Instagram</a>'
        ),
    },
}


async def check_and_send_quiz_followups(bot: Bot) -> None:
    """Check for users needing follow-up and send messages."""
    async with async_session() as session:
        users = await repo.get_quiz_followup_users(session)

    if not users:
        return

    now = datetime.now(timezone.utc)
    sent_count = 0

    for user in users:
        current_step = user.quiz_followup_step
        next_step = current_step + 1

        if next_step > 3:
            continue

        followup = FOLLOWUP_MESSAGES.get(next_step)
        if not followup:
            continue

        # Check if enough time has passed
        reference_time = user.quiz_followup_last_at or user.quiz_completed_at
        if not reference_time:
            continue

        # Ensure timezone-aware
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        hours_since = (now - reference_time).total_seconds() / 3600
        if hours_since < followup["delay_hours"]:
            continue

        # Build keyboard
        keyboard_buttons = []
        if next_step < 3:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="💳 Открыть доступ за 45 BYN",
                    callback_data="buy",
                )
            ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="📱 Открыть меню", callback_data="menu")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=followup["text"],
                reply_markup=keyboard,
            )
            sent_count += 1

            # Update step in DB
            async with async_session() as session:
                await repo.update_followup_step(session, user.id, next_step)

        except TelegramForbiddenError:
            logger.warning(
                "User %s blocked the bot during followup. Marking as blocked.",
                user.telegram_id,
            )
            async with async_session() as session:
                await repo.mark_user_blocked(session, user.telegram_id)
        except TelegramAPIError as exc:
            logger.error(
                "Failed to send followup step %d to user %s: %s",
                next_step,
                user.telegram_id,
                exc,
            )

    if sent_count:
        logger.info("Quiz followup: sent %d messages.", sent_count)
