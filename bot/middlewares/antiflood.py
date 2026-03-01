"""Simple anti-flood middleware using Redis throttle."""

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery


class AntiFloodMiddleware(BaseMiddleware):
    """Drop duplicate messages from the same user within ``rate_limit`` seconds."""

    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self._cache: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        import time

        user_id: int | None = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            now = time.monotonic()
            last = self._cache.get(user_id, 0.0)
            if now - last < self.rate_limit:
                return  # silently drop
            self._cache[user_id] = now

        return await handler(event, data)
