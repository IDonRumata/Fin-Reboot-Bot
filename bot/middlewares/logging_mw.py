"""Logging middleware — logs every incoming update."""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            logger.info(
                "Message from %s (%s): %s",
                event.from_user.id,
                event.from_user.username or "",
                (event.text or "")[:80],
            )
        elif isinstance(event, CallbackQuery) and event.from_user:
            logger.info(
                "Callback from %s: %s",
                event.from_user.id,
                event.data,
            )
        return await handler(event, data)
