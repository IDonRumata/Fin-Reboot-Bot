"""Continue-block callbacks: cont_d1_b2, cont_d1_b3, etc.

When user presses "Продолжить →", we send the next block of content.
"""

from __future__ import annotations

import logging
import re

from aiogram import Router, types, F, Bot
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repositories as repo
from bot.services.content_sender import send_day_block

logger = logging.getLogger(__name__)
router = Router(name="continue_block")

# Match cont_d1_b2, cont_d2_b3, etc.
CONTINUE_RE = re.compile(r"^cont_d(\d)_b(\d)$")


@router.callback_query(F.data.regexp(CONTINUE_RE))
async def cb_continue_block(
    callback: types.CallbackQuery,
    session: AsyncSession,
    bot: Bot,
) -> None:
    await callback.answer("Загружаю...", cache_time=5)

    if not callback.from_user or not callback.data:
        return

    match = CONTINUE_RE.match(callback.data)
    if not match:
        return

    day = int(match.group(1))
    block_num = int(match.group(2))

    user = await repo.get_user_by_telegram_id(session, callback.from_user.id)
    if not user:
        return

    # Send the requested block
    await send_day_block(
        bot=bot,
        session=session,
        telegram_id=callback.from_user.id,
        user_id=user.id,
        day=day,
        block_num=block_num,
    )
