"""Fallback handler for unknown messages."""

from __future__ import annotations

from aiogram import Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

router = Router(name="fallback")


@router.message()
async def fallback_message(message: types.Message) -> None:
    """Catch all unrecognized text messages."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Меню", callback_data="menu")],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
        ]
    )
    await message.answer(
        "🤔 Я не понимаю эту команду.\n\n"
        "Используйте кнопки ниже для навигации:",
        reply_markup=keyboard,
    )
