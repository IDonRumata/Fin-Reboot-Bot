"""AI assistant service using Groq API for answering user questions."""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp

from bot.core.config import settings
from bot.knowledge_base import ASSISTANT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Keywords that hint at a tax-related question — add disclaimer
TAX_KEYWORDS = ("налог", "ндфл", "декларац", "декларир", "налогооблаг", "мнс", "фнс", "нбрб")

# Maximum response tokens
MAX_TOKENS = 800


async def ask_pixi(user_message: str, user_name: Optional[str] = None) -> str:
    """
    Send user message to Groq and return Pixi's response.
    Falls back to a polite error message if Groq is unavailable.
    """
    if not settings.groq_api_key:
        return (
            "🤖 AI-ассистент временно недоступен.\n\n"
            "Задайте вопрос в поддержку: @ifireboy"
        )

    # Build system prompt — optionally personalise with name
    system = ASSISTANT_SYSTEM_PROMPT
    if user_name:
        system = f"Имя пользователя: {user_name}. Обращайся по имени, если уместно.\n\n" + system

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message},
    ]

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.4,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GROQ_API_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    answer = data["choices"][0]["message"]["content"].strip()
                    # Append tax disclaimer if relevant
                    if _is_tax_question(user_message):
                        answer += (
                            "\n\n⚠️ <i>Налоговые данные актуальны на 2025 год. "
                            "Проверяй актуальность: mns.gov.by (BY), nalog.gov.ru (RU).</i>"
                        )
                    return answer
                else:
                    body = await resp.text()
                    logger.error("Groq API error %s: %s", resp.status, body[:300])
                    return _fallback_response()
    except aiohttp.ClientError as exc:
        logger.error("Groq request failed: %s", exc)
        return _fallback_response()


def _is_tax_question(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in TAX_KEYWORDS)


def _fallback_response() -> str:
    return (
        "😔 Не могу ответить прямо сейчас — небольшие технические неполадки.\n\n"
        "Задайте вопрос напрямую в поддержку: @ifireboy\n"
        "Или попробуйте снова через минуту."
    )
