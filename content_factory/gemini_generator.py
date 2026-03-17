"""
Генератор контента через Gemini API.
Создаёт скрипты для видео, посты для Telegram/Instagram, подписи.
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, get_pushup_stats
from prompts.tiktok_scripts import TIKTOK_SCRIPT_PROMPT, CONTENT_TOPICS
from prompts.telegram_posts import TELEGRAM_POST_PROMPT
from prompts.instagram_captions import INSTAGRAM_CAPTION_PROMPT
from prompts.grafin_posts import GRAFIN_POST_PROMPT

_client = genai.Client(api_key=GEMINI_API_KEY)
_MODEL = "gemini-2.5-flash"
_GENERATE_CFG = types.GenerateContentConfig(
    temperature=0.85,
    max_output_tokens=2048,
)


def _get_model(model_name: str = _MODEL) -> str:
    return model_name


def _extract_block(text: str, tag: str) -> str:
    """Извлекает блок между ---TAG--- и ---КОНЕЦ---."""
    pattern = rf"---{tag}---\s*(.*?)\s*---КОНЕЦ---"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


def _fill_pushup_context(extra_context: str) -> str:
    """Подставляет актуальные данные челенджа в шаблон контекста."""
    stats = get_pushup_stats()
    return extra_context.format(
        day=stats["day"],
        count=stats["current_count"],
        year_end=stats["year_end_forecast"],
    )


class ContentGenerator:
    def __init__(self):
        self.model = _MODEL
        self.output_dir = Path("content_output")
        self.output_dir.mkdir(exist_ok=True)

    def generate_tiktok_script(self, topic_id: str) -> dict:
        """Генерирует скрипт для TikTok/Reels по ID темы."""
        topic_data = next((t for t in CONTENT_TOPICS if t["id"] == topic_id), None)
        if not topic_data:
            raise ValueError(f"Тема '{topic_id}' не найдена. Доступные: {[t['id'] for t in CONTENT_TOPICS]}")

        extra_context = topic_data.get("extra_context", "")
        # Подставляем актуальные данные отжиманий если нужно
        if "{day}" in extra_context or "{count}" in extra_context:
            extra_context = _fill_pushup_context(extra_context)

        prompt = TIKTOK_SCRIPT_PROMPT.format(
            topic=topic_data["topic"],
            format=topic_data.get("format", "информационный"),
            extra_context=extra_context,
        )
        response = _client.models.generate_content(model=self.model, contents=prompt, config=_GENERATE_CFG)
        raw = response.text

        result = {
            "topic_id": topic_id,
            "topic": topic_data["topic"],
            "series": topic_data.get("series", ""),
            "script": _extract_block(raw, "СКРИПТ"),
            "description": _extract_block(raw, "ОПИСАНИЕ ДЛЯ ПУБЛИКАЦИИ"),
            "ab_hooks": _extract_block(raw, "ХУКИ ДЛЯ A/B ТЕСТА"),
            "generated_at": datetime.now().isoformat(),
            "raw": raw,
        }
        self._save_result("tiktok", topic_id, result)
        return result

    def generate_telegram_post(self, topic: str, post_format: str = "информационный", extra_context: str = "") -> dict:
        """Генерирует пост для Telegram-канала."""
        prompt = TELEGRAM_POST_PROMPT.format(
            topic=topic,
            format=post_format,
            extra_context=extra_context,
        )
        response = _client.models.generate_content(model=self.model, contents=prompt, config=_GENERATE_CFG)
        result = {
            "topic": topic,
            "post": _extract_block(response.text, "ПОСТ"),
            "generated_at": datetime.now().isoformat(),
        }
        self._save_result("telegram", topic[:30], result)
        return result

    def generate_grafin_post(self, topic: str, post_type: str = "разбор", extra_context: str = "") -> dict:
        """Генерирует пост для канала ГраФин."""
        prompt = GRAFIN_POST_PROMPT.format(
            topic=topic,
            post_type=post_type,
            extra_context=extra_context,
        )
        response = _client.models.generate_content(model=self.model, contents=prompt, config=_GENERATE_CFG)
        result = {
            "topic": topic,
            "post_type": post_type,
            "post": _extract_block(response.text, "ПОСТ"),
            "generated_at": datetime.now().isoformat(),
        }
        self._save_result("grafin", topic[:30], result)
        return result

    def generate_instagram_caption(self, topic: str, extra_context: str = "") -> dict:
        """Генерирует подпись для Instagram."""
        prompt = INSTAGRAM_CAPTION_PROMPT.format(
            topic=topic,
            extra_context=extra_context,
        )
        response = _client.models.generate_content(model=self.model, contents=prompt, config=_GENERATE_CFG)
        result = {
            "topic": topic,
            "caption": _extract_block(response.text, "ПОДПИСЬ"),
            "generated_at": datetime.now().isoformat(),
        }
        self._save_result("instagram", topic[:30], result)
        return result

    def generate_full_content_package(self, topic_id: str) -> dict:
        """
        Генерирует полный пакет контента для одной темы:
        скрипт TikTok + пост Telegram + пост ГраФин + подпись Instagram.
        """
        topic_data = next((t for t in CONTENT_TOPICS if t["id"] == topic_id), None)
        if not topic_data:
            raise ValueError(f"Тема '{topic_id}' не найдена.")

        extra_context = topic_data.get("extra_context", "")
        if "{day}" in extra_context or "{count}" in extra_context:
            extra_context = _fill_pushup_context(extra_context)

        topic = topic_data["topic"]
        print(f"🎬 Генерирую пакет для темы: {topic[:50]}...")

        tiktok = self.generate_tiktok_script(topic_id)
        print("  ✅ TikTok скрипт")

        telegram = self.generate_telegram_post(topic, topic_data.get("format", ""), extra_context)
        print("  ✅ Telegram пост")

        grafin = self.generate_grafin_post(topic, "разбор", extra_context)
        print("  ✅ ГраФин пост")

        instagram = self.generate_instagram_caption(topic, extra_context)
        print("  ✅ Instagram подпись")

        package = {
            "topic_id": topic_id,
            "topic": topic,
            "series": topic_data.get("series", ""),
            "tiktok_script": tiktok["script"],
            "tiktok_description": tiktok["description"],
            "ab_hooks": tiktok["ab_hooks"],
            "telegram_post": telegram["post"],
            "grafin_post": grafin["post"],
            "instagram_caption": instagram["caption"],
            "generated_at": datetime.now().isoformat(),
        }
        self._save_result("package", topic_id, package)
        return package

    def _save_result(self, content_type: str, name: str, data: dict):
        """Сохраняет результат в JSON-файл."""
        safe_name = re.sub(r"[^\w\-]", "_", name)[:40]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.output_dir / f"{content_type}_{safe_name}_{timestamp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_topics(self) -> None:
        """Выводит список доступных тем."""
        print("\n📋 Доступные темы для контента:\n")
        current_series = ""
        for t in CONTENT_TOPICS:
            if t.get("series") != current_series:
                current_series = t.get("series", "")
                series_names = {
                    "pushup_invest": "🏋️ Серия: Челендж + Инвестиции",
                    "trucker_explains": "🚛 Серия: Дальнобойщик объясняет",
                    "myths": "💥 Серия: Разрушение мифов",
                    "education": "📚 Серия: Образование",
                    "belarus": "🇧🇾 Серия: Беларусь",
                }
                print(f"\n{series_names.get(current_series, current_series)}")
            print(f"  [{t['id']}] {t['topic'][:70]}")


if __name__ == "__main__":
    gen = ContentGenerator()
    gen.list_topics()
