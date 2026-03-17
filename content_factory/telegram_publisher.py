"""
Отправка сгенерированного контента Андрею на ревью в Telegram.
Кнопки: ✅ Опубликовать в ГраФин / ✏️ Пересоздать / ❌ Отклонить
После одобрения — публикует в канал ГраФин.
"""
import asyncio
import json
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command

from config import TELEGRAM_BOT_TOKEN, ANDREY_TELEGRAM_ID, GRAFIN_CHANNEL_ID
from gemini_generator import ContentGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

generator = ContentGenerator()

# Временное хранилище ожидающих одобрения пакетов {message_id: package_data}
pending_packages: dict[int, dict] = {}


def _approval_keyboard(topic_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать в ГраФин", callback_data=f"pub_grafin:{topic_id}"),
        ],
        [
            InlineKeyboardButton(text="📢 Опубликовать везде", callback_data=f"pub_all:{topic_id}"),
        ],
        [
            InlineKeyboardButton(text="🔄 Пересоздать", callback_data=f"regen:{topic_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{topic_id}"),
        ],
    ])


async def send_package_for_review(package: dict) -> int:
    """Отправляет пакет контента Андрею на ревью. Возвращает message_id."""
    stats_line = ""
    if "pushup" in package.get("series", ""):
        from config import get_pushup_stats
        s = get_pushup_stats()
        stats_line = f"\n📊 Челендж: день {s['day']}, {s['current_count']} отжиманий\n"

    preview = (
        f"📦 <b>Новый контент-пакет готов!</b>\n"
        f"🏷 Тема: <i>{package['topic'][:80]}</i>\n"
        f"📂 Серия: {package.get('series', '—')}"
        f"{stats_line}\n"
        f"{'─' * 30}\n\n"
        f"🎬 <b>СКРИПТ TIKTOK/REELS:</b>\n{package['tiktok_script']}\n\n"
        f"{'─' * 30}\n"
        f"📱 <b>ПОСТ GRAFIN:</b>\n{package['grafin_post']}\n\n"
        f"{'─' * 30}\n"
        f"📲 <b>INSTAGRAM:</b>\n{package['instagram_caption']}\n\n"
        f"{'─' * 30}\n"
        f"🧪 <b>A/B ХУКИ (для теста):</b>\n{package['ab_hooks']}"
    )

    # Telegram ограничивает сообщение ~4096 символов — режем если нужно
    if len(preview) > 4000:
        preview = preview[:3900] + "\n\n... [обрезано, полный вариант в файле]"

    msg = await bot.send_message(
        chat_id=ANDREY_TELEGRAM_ID,
        text=preview,
        parse_mode="HTML",
        reply_markup=_approval_keyboard(package["topic_id"]),
    )
    pending_packages[msg.message_id] = package
    return msg.message_id


@router.callback_query(F.data.startswith("pub_grafin:"))
async def publish_to_grafin(callback: CallbackQuery):
    topic_id = callback.data.split(":", 1)[1]
    package = _find_package(topic_id)
    if not package:
        await callback.answer("❌ Пакет не найден (устарел?)")
        return

    await bot.send_message(
        chat_id=GRAFIN_CHANNEL_ID,
        text=package["grafin_post"],
        parse_mode="Markdown",
    )
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Опубликовано в ГраФин!</b>",
        parse_mode="HTML",
    )
    await callback.answer("✅ Опубликовано!")
    logger.info(f"Published to ГраФин: {topic_id}")


@router.callback_query(F.data.startswith("pub_all:"))
async def publish_everywhere(callback: CallbackQuery):
    topic_id = callback.data.split(":", 1)[1]
    package = _find_package(topic_id)
    if not package:
        await callback.answer("❌ Пакет не найден")
        return

    # Публикуем в ГраФин
    await bot.send_message(
        chat_id=GRAFIN_CHANNEL_ID,
        text=package["grafin_post"],
        parse_mode="Markdown",
    )
    # Сохраняем пакет в файл для ручной публикации в TikTok/Instagram
    output_path = Path("content_output") / f"approved_{topic_id}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False, indent=2)

    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ <b>Опубликовано везде!</b>\nФайл: {output_path}",
        parse_mode="HTML",
    )
    await callback.answer("✅ Опубликовано!")


@router.callback_query(F.data.startswith("regen:"))
async def regenerate(callback: CallbackQuery):
    topic_id = callback.data.split(":", 1)[1]
    await callback.answer("🔄 Пересоздаю...")
    await callback.message.edit_text(
        callback.message.text + "\n\n🔄 <i>Пересоздание...</i>",
        parse_mode="HTML",
    )
    try:
        new_package = generator.generate_full_content_package(topic_id)
        await send_package_for_review(new_package)
        await callback.message.delete()
    except Exception as e:
        await bot.send_message(ANDREY_TELEGRAM_ID, f"❌ Ошибка пересоздания: {e}")


@router.callback_query(F.data.startswith("reject:"))
async def reject_content(callback: CallbackQuery):
    topic_id = callback.data.split(":", 1)[1]
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>Отклонено</b>",
        parse_mode="HTML",
    )
    await callback.answer("❌ Отклонено")


@router.message(Command("generate"))
async def cmd_generate(message: Message):
    """Ручная генерация: /generate pushup_invest_1"""
    if message.from_user.id != ANDREY_TELEGRAM_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        available = ", ".join([t["id"] for t in __import__("prompts.tiktok_scripts", fromlist=["CONTENT_TOPICS"]).CONTENT_TOPICS])
        await message.reply(f"Использование: /generate <topic_id>\n\nДоступные темы:\n{available}")
        return

    topic_id = parts[1]
    await message.reply(f"⏳ Генерирую пакет для '{topic_id}'...")
    try:
        package = generator.generate_full_content_package(topic_id)
        await send_package_for_review(package)
    except ValueError as e:
        await message.reply(f"❌ {e}")
    except Exception as e:
        await message.reply(f"❌ Ошибка Gemini API: {e}")


@router.message(Command("topics"))
async def cmd_topics(message: Message):
    """Список доступных тем: /topics"""
    if message.from_user.id != ANDREY_TELEGRAM_ID:
        return
    from prompts.tiktok_scripts import CONTENT_TOPICS
    lines = ["📋 <b>Доступные темы:</b>\n"]
    for t in CONTENT_TOPICS:
        lines.append(f"• <code>{t['id']}</code> — {t['topic'][:60]}")
    await message.reply("\n".join(lines), parse_mode="HTML")


def _find_package(topic_id: str) -> dict | None:
    """Ищет пакет в pending по topic_id."""
    for package in pending_packages.values():
        if package.get("topic_id") == topic_id:
            return package
    return None


async def main():
    logger.info("🚀 Content Publisher Bot запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
