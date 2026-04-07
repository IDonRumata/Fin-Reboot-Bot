"""Day-done callbacks: day_1_done .. day_5_done.

When user presses the completion button, we mark the day as completed
and show a progress bar.
"""

from __future__ import annotations

import asyncio
import logging
import re

from aiogram import Router, types, F
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repositories as repo
from bot.services.user_service import build_progress_text

logger = logging.getLogger(__name__)
router = Router(name="day_done")

# Match day_1_done, day_2_done, ... day_5_done
DAY_DONE_RE = re.compile(r"^day_(\d)_done$")


@router.callback_query(F.data.regexp(DAY_DONE_RE))
async def cb_day_done(callback: types.CallbackQuery, session: AsyncSession) -> None:
    await callback.answer("✅ Отлично!", cache_time=5)

    if not callback.from_user or not callback.data:
        return

    match = DAY_DONE_RE.match(callback.data)
    if not match:
        return

    day = int(match.group(1))
    user = await repo.get_user_by_telegram_id(session, callback.from_user.id)
    if not user:
        return

    # Mark day as completed
    await repo.mark_day_completed(session, user.id, day)

    # Refresh progress and show
    progress = await repo.get_progress(session, user.id)
    if not progress:
        return

    progress_text = build_progress_text(progress)

    if day < 5:
        text = (
            f"🎉 <b>День {day} выполнен!</b>\n\n"
            f"{progress_text}\n\n"
            "Следующий день откроется завтра. ⏰"
        )
    else:
        text = (
            "🎓 <b>Поздравляем! Курс пройден!</b>\n\n"
            f"{progress_text}\n\n"
            "Спасибо, что прошли курс с нами! 💪"
        )

    if callback.message:
        await callback.message.answer(text)  # type: ignore[union-attr]

        # Social links after course completion (day 5)
        if day == 5:
            await asyncio.sleep(3)
            socials_text = (
                "📱 <b>Оставайтесь с нами</b>\n\n"
                "Марина:\n"
                '<a href="https://tiktok.com/@dementjeva17">TikTok</a>  '
                '<a href="https://youtube.com/@МаринаДементьева/shorts">YouTube</a>  '
                '<a href="https://instagram.com/marina_dementjeva">Instagram</a>\n\n'
                "Андрей:\n"
                '<a href="https://tiktok.com/@krononchill">TikTok</a>  '
                '<a href="https://youtube.com/@andreimarozv">YouTube</a>  '
                '<a href="https://instagram.com/krononchill">Instagram</a>'
            )
            try:
                await callback.message.answer(  # type: ignore[union-attr]
                    socials_text,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass

            await asyncio.sleep(3)
            plan_text = (
                "📅 <b>Твой план на первые 90 дней</b>\n\n"
                "Курс пройден - теперь главное не останавливаться. Вот конкретный план:\n\n"
                "<b>30 дней - фундамент</b>\n"
                "✅ Заполнить Финансовый рентген и найти «дыры» в расходах\n"
                "✅ Открыть депозит в USD/EUR для подушки безопасности\n"
                "✅ Определить сумму для ежемесячного инвестирования\n\n"
                "<b>60 дней - первые шаги</b>\n"
                "✅ Открыть счёт у брокера (Freedom Finance или Interactive Brokers)\n"
                "✅ Сделать первую покупку ETF на S&P 500\n"
                "✅ Настроить напоминание для регулярных пополнений\n\n"
                "<b>90 дней - система работает</b>\n"
                "✅ Сделать 2-3 регулярные покупки по стратегии DCA\n"
                "✅ Проверить портфель (без паники при колебаниях!)\n"
                "✅ Посчитать сложный процент со своими цифрами на 10 лет\n\n"
                "Самое сложное - начать. Ты уже сделал(а) это, пройдя курс. "
                "Следующий шаг - первая реальная покупка. Удачи! 🚀"
            )
            try:
                await callback.message.answer(plan_text)  # type: ignore[union-attr]
            except Exception:
                pass
