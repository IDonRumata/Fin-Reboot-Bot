"""/start handler - user registration with deep linking UTM tracking."""

from __future__ import annotations

import logging

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import settings
from bot.database import repositories as repo

logger = logging.getLogger(__name__)
router = Router(name="start")


def _parse_deep_link(args: str | None) -> dict[str, str | None]:
    """Parse utm parameters from deep link: utm_source__utm_medium__utm_campaign."""
    result: dict[str, str | None] = {
        "utm_source": None,
        "utm_medium": None,
        "utm_campaign": None,
    }
    if not args:
        return result
    parts = args.split("__")
    if len(parts) >= 1:
        result["utm_source"] = parts[0]
    if len(parts) >= 2:
        result["utm_medium"] = parts[1]
    if len(parts) >= 3:
        result["utm_campaign"] = parts[2]
    return result


WELCOME_TEXT = (
    "━━━━━━━━━━━━━━━━━━━\n"
    "🔥 <b>Графин</b> - грамотность финансовая\n"
    "━━━━━━━━━━━━━━━━━━━\n\n"
    "Добро пожаловать! За <b>5 дней</b> вы:\n\n"
    "📊 День 1 - Узнаете, куда утекают деньги\n"
    "🛡 День 2 - Создадите стратегию защиты\n"
    "₿ День 3 - Откроете криптокошелёк\n"
    "📈 День 4 - Откроете брокерский счёт\n"
    "🏆 День 5 - Соберёте портфель\n\n"
    "Автор - <b>Марина Дементьева</b>, "
    "20 лет в инвестициях, с 2010 года живёт на пассивный доход.\n\n"
    "👇 Выберите действие:"
)


@router.message(CommandStart())
async def cmd_start(message: types.Message, session: AsyncSession, state: FSMContext) -> None:
    if not message.from_user:
        return

    # Parse deep link
    args = message.text.split(maxsplit=1)[1] if message.text and " " in message.text else None

    # ── Quiz funnel: deep link starts with quiz_ ──
    if args and args.startswith("quiz_"):
        utm_source = args  # e.g. "quiz_instagram"
        await repo.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            utm_source=utm_source,
        )
        from bot.handlers.quiz import start_quiz
        await start_quiz(message, state)
        return

    # ── Standard flow ──
    utm = _parse_deep_link(args)

    # Register/update user
    await repo.get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        utm_source=utm["utm_source"],
        utm_medium=utm["utm_medium"],
        utm_campaign=utm["utm_campaign"],
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Купить курс", callback_data="buy")],
            [InlineKeyboardButton(text="📋 О программе", callback_data="about")],
            [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="progress")],
            [InlineKeyboardButton(
                text="🧮 Калькулятор инвестора",
                url=settings.webapp_calc_url,
            )],
            [InlineKeyboardButton(
                text="📉 Финансовый рентген",
                url=settings.webapp_tracker_url,
            )],
            [InlineKeyboardButton(text="📝 Шпаргалка по налогам", callback_data="tax_cheatsheet")],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
            [InlineKeyboardButton(text="📜 Оферта", callback_data="oferta")],
        ]
    )

    await message.answer(WELCOME_TEXT, reply_markup=keyboard)


