"""Keyword triggers: АРЕНДА and РОБОТ."""

from __future__ import annotations

import logging

from aiogram import Router, types, F
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import settings
from bot.database import repositories as repo
from bot.database.models import LeadType

logger = logging.getLogger(__name__)
router = Router(name="keywords")


@router.message(F.text.casefold().contains("аренда"))
async def kw_arenda(message: types.Message, session: AsyncSession) -> None:
    if not message.from_user:
        return

    user = await repo.get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    is_new = await repo.save_lead(session, user.id, LeadType.arenda)

    if is_new:
        text = (
            "🏠 <b>Отлично!</b>\n\n"
            "Мы записали вас в список ожидания курса по арендной недвижимости.\n\n"
            "Вы получите уведомление сразу, как только курс будет готов. 📩"
        )
    else:
        text = (
            "🏠 Вы уже в списке ожидания курса по аренде.\n"
            "Мы обязательно вас уведомим! 👍"
        )

    await message.answer(text)


@router.message(F.text.casefold().contains("робот"))
async def kw_robot(message: types.Message, session: AsyncSession) -> None:
    if not message.from_user:
        return

    user = await repo.get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    is_new = await repo.save_lead(session, user.id, LeadType.robot)

    if is_new:
        text = (
            "🤖 <b>Форекс-робот</b>\n\n"
            "Отлично! Для записи на бесплатный месяц тестирования "
            "напишите боту 👉 @TestDriveFXrobot\n\n"
            "🎁 Первый месяц – бесплатно на демо-счёте!\n"
            "Бесплатная настройка от специалиста."
        )
    else:
        text = (
            "🤖 Вы уже оставляли заявку на робота.\n"
            "Напишите боту для записи: @TestDriveFXrobot"
        )

    await message.answer(text)
