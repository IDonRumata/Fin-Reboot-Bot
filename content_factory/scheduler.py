"""
Планировщик задач контент-завода.
Запускает еженедельную генерацию контента, ежедневные отчёты.
Запускать как: python scheduler.py
"""
import asyncio
import logging
import random
from datetime import datetime

import schedule
import time

from config import ANDREY_TELEGRAM_ID, TELEGRAM_BOT_TOKEN, get_pushup_stats
from gemini_generator import ContentGenerator
from telegram_publisher import send_package_for_review

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("content_factory.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from aiogram import Bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
generator = ContentGenerator()


# ── Недельные темы: один пакет в понедельник, один в четверг ──────────────────

WEEKLY_TOPICS = [
    # Неделя 1
    ["pushup_invest_1", "myth_1"],
    # Неделя 2
    ["trucker_1", "edu_dca"],
    # Неделя 3
    ["pushup_invest_2", "edu_etf"],
    # Неделя 4
    ["trucker_2", "myth_2"],
    # Неделя 5
    ["pushup_invest_3", "by_tax"],
    # Неделя 6
    ["trucker_3", "edu_compound"],
    # Неделя 7
    ["myth_3", "by_broker"],
]

_week_index = 0


def _get_topics_for_this_week() -> list[str]:
    global _week_index
    week_num = datetime.now().isocalendar()[1]
    return WEEKLY_TOPICS[week_num % len(WEEKLY_TOPICS)]


async def _generate_and_send(topic_id: str):
    """Генерирует пакет и отправляет на ревью."""
    logger.info(f"Генерирую пакет: {topic_id}")
    try:
        package = generator.generate_full_content_package(topic_id)
        await send_package_for_review(package)
        logger.info(f"✅ Пакет отправлен на ревью: {topic_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка генерации {topic_id}: {e}")
        await bot.send_message(ANDREY_TELEGRAM_ID, f"❌ Ошибка генерации контента ({topic_id}): {e}")


async def weekly_content_monday():
    """Каждый понедельник — генерация первой темы недели."""
    topics = _get_topics_for_this_week()
    await _generate_and_send(topics[0])


async def weekly_content_thursday():
    """Каждый четверг — генерация второй темы недели."""
    topics = _get_topics_for_this_week()
    if len(topics) > 1:
        await _generate_and_send(topics[1])


async def daily_pushup_post():
    """Каждое утро — обновление по челенджу с отжиманиями для ГраФин."""
    stats = get_pushup_stats()
    # Отправляем только в дни кратные 7 (раз в неделю) или день 100, 200, 300, 365
    milestone_days = {100, 144, 200, 250, 300, 365}
    if stats["day"] % 7 == 0 or stats["day"] in milestone_days:
        await _generate_and_send("pushup_invest_3")


async def daily_stats_report():
    """Ежедневный отчёт в Telegram Андрею."""
    stats = get_pushup_stats()
    report = (
        f"📊 <b>Ежедневный отчёт контент-завода</b>\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"🏋️ Челендж: день {stats['day']}, {stats['current_count']} отжиманий\n"
        f"📈 До конца года: ещё {365 - stats['day']} дней\n"
        f"🎯 Прогноз на 31.10.2026: {stats['year_end_forecast']} отжиманий\n\n"
        f"Для генерации контента: /generate &lt;topic_id&gt;\n"
        f"Список тем: /topics"
    )
    await bot.send_message(ANDREY_TELEGRAM_ID, report, parse_mode="HTML")


def _run_async(coro):
    """Запускает async функцию из sync контекста."""
    asyncio.get_event_loop().run_until_complete(coro)


def setup_schedule():
    # Понедельник 09:00 — первая тема недели
    schedule.every().monday.at("09:00").do(lambda: _run_async(weekly_content_monday()))
    # Четверг 09:00 — вторая тема недели
    schedule.every().thursday.at("09:00").do(lambda: _run_async(weekly_content_thursday()))
    # Ежедневно 08:30 — проверка миллстоунов челенджа
    schedule.every().day.at("08:30").do(lambda: _run_async(daily_pushup_post()))
    # Ежедневно 08:00 — краткий отчёт
    schedule.every().day.at("08:00").do(lambda: _run_async(daily_stats_report()))

    logger.info("✅ Расписание настроено:")
    logger.info("  Пн 09:00 — Генерация контента (тема 1)")
    logger.info("  Чт 09:00 — Генерация контента (тема 2)")
    logger.info("  Ежедн. 08:30 — Проверка миллстоунов отжиманий")
    logger.info("  Ежедн. 08:00 — Ежедневный отчёт")


def main():
    setup_schedule()
    logger.info("🚀 Планировщик контент-завода запущен")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
