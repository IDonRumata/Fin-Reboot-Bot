"""/progress handler - show course progress bar."""

from __future__ import annotations

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repositories as repo
from bot.services.user_service import build_progress_text

router = Router(name="progress")


async def _show_progress(target: types.Message | types.CallbackQuery, session: AsyncSession) -> None:
    from_user = target.from_user
    if not from_user:
        return

    user = await repo.get_user_by_telegram_id(session, from_user.id)
    if not user:
        return

    progress = await repo.get_progress(session, user.id)
    if not progress:
        text = "Вы ещё не начали курс. Нажмите /start"
    else:
        text = build_progress_text(progress)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Меню", callback_data="menu")],
        ]
    )

    if isinstance(target, types.CallbackQuery):
        await target.answer()
        if target.message:
            await target.message.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]
    else:
        await target.answer(text, reply_markup=keyboard)


@router.message(Command("progress"))
async def cmd_progress(message: types.Message, session: AsyncSession) -> None:
    await _show_progress(message, session)


@router.callback_query(F.data == "progress")
async def cb_progress(callback: types.CallbackQuery, session: AsyncSession) -> None:
    await _show_progress(callback, session)
