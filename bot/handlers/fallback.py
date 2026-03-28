"""Fallback handler — routes unrecognised messages to Pixi AI assistant."""

from __future__ import annotations

import logging

from aiogram import Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.core.config import settings
from bot.services.ai_assistant import ask_pixi

logger = logging.getLogger(__name__)
router = Router(name="fallback")


@router.message()
async def fallback_message(message: types.Message) -> None:
    """Catch all unrecognised text messages — answer via Pixi if AI is enabled."""
    if not message.text or not message.from_user:
        return

    # If Groq is configured — use AI assistant
    if settings.groq_api_key:
        # Show typing indicator while waiting for AI
        await message.bot.send_chat_action(  # type: ignore[union-attr]
            chat_id=message.chat.id,
            action="typing",
        )

        user_name = message.from_user.first_name or None
        answer = await ask_pixi(message.text, user_name=user_name)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📱 Меню", callback_data="menu")],
                [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
            ]
        )
        await message.answer(answer, reply_markup=keyboard, parse_mode="HTML")
        logger.info(
            "Pixi answered user %s (len=%d): %.80s",
            message.from_user.id,
            len(answer),
            message.text,
        )

    else:
        # Fallback when no AI key configured
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📱 Меню", callback_data="menu")],
                [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
            ]
        )
        await message.answer(
            "🤔 Не совсем понимаю вопрос.\n\n"
            "Используйте кнопки ниже или напишите в поддержку @ifireboy:",
            reply_markup=keyboard,
        )
