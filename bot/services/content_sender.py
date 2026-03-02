"""Content delivery engine — replaces Fin_Reboot_Send_Content_v2 workflow.

Core function: send a sequence of content blocks to a user with delays,
handling all 7 content types and errors gracefully.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Sequence

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repositories as repo
from bot.database.models import ContentBlock, ContentType

logger = logging.getLogger(__name__)


def _is_real_file_id(file_id: str | None) -> bool:
    """Check if file_id is a real Telegram file_id or a local file."""
    if not file_id or not file_id.strip():
        return False
    fid = file_id.strip()
    if fid.startswith("["):
        return False
    # Allow local files
    if fid.endswith(".png") or fid.endswith(".jpg"):
        return True
    if len(fid) < 20:
        return False
    return True


async def send_single_block(
    bot: Bot,
    chat_id: int,
    block: ContentBlock,
) -> bool:
    """Send one content block. Returns True on success, False on skip/error."""

    content_type = block.type
    text = block.content or ""
    file_id = block.file_id or ""
    caption = block.caption or ""
    parse_mode = block.parse_mode or "HTML"

    try:
        match content_type:
            case ContentType.text:
                if text:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=parse_mode,
                    )
                else:
                    return False

            case ContentType.text_with_button:
                if not text or not block.button_text:
                    return False
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=block.button_text,
                                callback_data=block.button_callback or "noop",
                            )
                        ]
                    ]
                )
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=parse_mode,
                )

            case ContentType.text_with_webapp:
                if not text or not block.button_text:
                    return False
                from bot.core.config import settings

                # Determine webapp URL from button_callback
                webapp_urls = {
                    "calc": settings.webapp_calc_url,
                    "tracker": settings.webapp_tracker_url,
                }
                webapp_url = webapp_urls.get(
                    block.button_callback or "calc",
                    settings.webapp_calc_url,
                )
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=block.button_text,
                                url=webapp_url,
                            )
                        ]
                    ]
                )
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=parse_mode,
                )

            case ContentType.photo:
                if not _is_real_file_id(file_id):
                    logger.warning("Skipping photo block %s — no real file_id", block.id)
                    return False
                
                photo_obj = file_id
                if file_id.endswith(".png") or file_id.endswith(".jpg"):
                    local_path = f"/app/slides/{file_id}"
                    if not os.path.exists(local_path):
                        logger.warning("Local photo not found: %s", local_path)
                        return False
                    photo_obj = FSInputFile(local_path)

                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_obj,
                    caption=caption or None,
                    parse_mode=parse_mode if caption else None,
                )

            case ContentType.video:
                if not _is_real_file_id(file_id):
                    logger.warning("Skipping video block %s — no real file_id", block.id)
                    return False
                await bot.send_video(
                    chat_id=chat_id,
                    video=file_id,
                    caption=caption or None,
                    parse_mode=parse_mode if caption else None,
                )

            case ContentType.video_note:
                if not _is_real_file_id(file_id):
                    logger.warning("Skipping video_note block %s — no real file_id", block.id)
                    return False
                await bot.send_video_note(
                    chat_id=chat_id,
                    video_note=file_id,
                )

            case ContentType.voice:
                if not _is_real_file_id(file_id):
                    logger.warning("Skipping voice block %s — no real file_id", block.id)
                    return False
                await bot.send_voice(
                    chat_id=chat_id,
                    voice=file_id,
                )

            case _:
                logger.warning("Unknown content type: %s", content_type)
                return False

        return True

    except TelegramForbiddenError:
        raise  # propagate to caller to mark user as blocked
    except TelegramAPIError as exc:
        logger.error(
            "Telegram API error sending block %s (type=%s) to %s: %s",
            block.id,
            content_type,
            chat_id,
            exc,
        )
        return False  # continueOnFail


async def send_day_block(
    bot: Bot,
    session: AsyncSession,
    telegram_id: int,
    user_id: int,
    day: int,
    block_num: int,
) -> None:
    """Send all content items for a specific day/block to user.

    Handles: delays between messages, skip broken media, mark blocked users.
    """
    blocks: Sequence[ContentBlock] = await repo.get_content_blocks(session, day, block_num)

    if not blocks:
        logger.info("No blocks found for day=%s block=%s", day, block_num)
        return

    # Mark day as sent on first block
    if block_num == 1:
        await repo.mark_day_sent(session, user_id, day)

    # Update current block
    await repo.update_current_block(session, user_id, day, block_num)

    for i, block in enumerate(blocks):
        try:
            success = await send_single_block(bot, telegram_id, block)
            if success and block.delay_seconds > 0 and i < len(blocks) - 1:
                await asyncio.sleep(block.delay_seconds)
        except TelegramForbiddenError:
            logger.warning("User %s blocked the bot. Marking as blocked.", telegram_id)
            await repo.mark_user_blocked(session, telegram_id)
            return


DAY_GREETINGS = {
    1: "Сегодня мы начинаем наш путь к финансовой свободе! 🚀",
    2: "Продолжаем! Сегодня — стратегия защиты денег 🛡",
    3: "Отлично, ты уже на полпути! Сегодня — криптокошелёк ₿",
    4: "Почти у цели! Сегодня — брокерский счёт 📈",
    5: "Финальный рывок! Собираем портфель 🏆",
}


async def send_full_day(
    bot: Bot,
    session: AsyncSession,
    telegram_id: int,
    user_id: int,
    day: int,
) -> None:
    """Send ONLY the first block of a day (further blocks are gated by continue-buttons)."""
    # Personalized greeting at the start of each day
    user = await repo.get_user_by_telegram_id(session, telegram_id)
    first_name = user.first_name if user else None
    name = first_name or "друг"
    greeting = DAY_GREETINGS.get(day, "")
    text = f"👋 <b>{name}, привет!</b>\n\n📅 <b>День {day}.</b> {greeting}"
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
        await asyncio.sleep(2)
    except TelegramForbiddenError:
        raise
    except TelegramAPIError as exc:
        logger.error("Failed to send greeting to %s: %s", telegram_id, exc)

    await send_day_block(bot, session, telegram_id, user_id, day, block_num=1)
