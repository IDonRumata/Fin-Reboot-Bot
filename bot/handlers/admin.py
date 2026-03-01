"""Admin commands: /admin, /sync, /test_send, /confirm_payment."""

from __future__ import annotations

import csv
import logging
from io import StringIO
from pathlib import Path

from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import settings
from bot.database import repositories as repo
from bot.database.engine import async_session
from bot.database.models import ContentBlock, ContentType, PaymentStatus
from bot.services.content_sender import send_full_day

logger = logging.getLogger(__name__)
router = Router(name="admin")


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: types.Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return

    text = (
        "🛠 <b>Админ-панель</b>\n\n"
        "Доступные команды:\n\n"
        "/sync – Загрузить контент из CSV файла\n"
        "/test_send <code>telegram_id day</code> – Тестовая отправка контента\n"
        "/confirm_payment <code>telegram_id</code> – Подтвердить оплату вручную\n"
        "/stats – Статистика бота"
    )
    await message.answer(text)


@router.message(Command("stats"))
async def cmd_stats(message: types.Message, session: AsyncSession) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    from sqlalchemy import select, func
    from bot.database.models import User, UserProgress, DayStatus, Lead, LeadType

    # Total users
    total = (await session.execute(select(func.count(User.id)))).scalar() or 0
    paid = (await session.execute(
        select(func.count(User.id)).where(User.payment_status == PaymentStatus.paid)
    )).scalar() or 0

    # Day completions
    day_stats = []
    for d in range(1, 6):
        attr = f"day_{d}_status"
        count = (await session.execute(
            select(func.count(UserProgress.id)).where(
                getattr(UserProgress, attr) == DayStatus.completed
            )
        )).scalar() or 0
        day_stats.append(f"  День {d}: {count}")

    # Leads
    arenda = (await session.execute(
        select(func.count(Lead.id)).where(Lead.lead_type == LeadType.arenda)
    )).scalar() or 0
    robot = (await session.execute(
        select(func.count(Lead.id)).where(Lead.lead_type == LeadType.robot)
    )).scalar() or 0

    conversion = f"{paid/total*100:.1f}%" if total > 0 else "0%"

    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👤 Всего: {total}\n"
        f"💰 Оплатили: {paid}\n"
        f"📈 Конверсия: {conversion}\n\n"
        "<b>Прохождение дней:</b>\n" +
        "\n".join(day_stats) +
        f"\n\n<b>Лиды:</b>\n"
        f"  🏠 АРЕНДА: {arenda}\n"
        f"  🤖 РОБОТ: {robot}"
    )
    await message.answer(text)


@router.message(Command("test_send"))
async def cmd_test_send(message: types.Message, session: AsyncSession, bot: Bot) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Использование: /test_send <code>telegram_id day</code>")
        return

    try:
        telegram_id = int(parts[1])
        day = int(parts[2])
    except ValueError:
        await message.answer("Неверный формат. Пример: /test_send 123456789 1")
        return

    user = await repo.get_user_by_telegram_id(session, telegram_id)
    if not user:
        await message.answer(f"Пользователь {telegram_id} не найден.")
        return

    await message.answer(f"🚀 Отправляю день {day} пользователю {telegram_id}...")
    await send_full_day(bot, session, telegram_id, user.id, day)
    await message.answer("✅ Отправлено!")


@router.message(Command("confirm_payment"))
async def cmd_confirm_payment(
    message: types.Message, session: AsyncSession, bot: Bot
) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /confirm_payment <code>telegram_id</code>")
        return

    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный формат.")
        return

    user = await repo.get_user_by_telegram_id(session, telegram_id)
    if not user:
        await message.answer(f"Пользователь {telegram_id} не найден.")
        return

    await repo.confirm_payment(session, user.id, transaction_id="manual_admin")

    # Notify user
    confirm_text = (
        "━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Спасибо за покупку программы «Финансовая перезагрузка»! 🎉\n\n"
        "👉 Присоединяйтесь к нашему чату участников "
        "для общения и обратной связи:\n"
        f"{settings.participants_chat_url}\n\n"
        "📚 Первый день программы начнётся через несколько секунд!"
    )
    try:
        await bot.send_message(chat_id=telegram_id, text=confirm_text)
    except Exception as exc:
        logger.error("Failed to notify user %s: %s", telegram_id, exc)

    # Trigger Day 1
    import asyncio
    await asyncio.sleep(5)
    await send_full_day(bot, session, telegram_id, user.id, day=1)

    await message.answer(f"✅ Оплата для {telegram_id} подтверждена, День 1 отправлен.")


@router.message(Command("sync"))
async def cmd_sync(message: types.Message, session: AsyncSession) -> None:
    """Reload content_blocks from CSV file into database."""
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    csv_path = Path(__file__).parent.parent.parent / "data" / "content_blocks.csv"
    if not csv_path.exists():
        await message.answer(f"❌ Файл не найден: {csv_path}")
        return

    await message.answer("⏳ Загружаю контент из CSV...")

    try:
        count = await _import_csv(session, csv_path)
        await message.answer(f"✅ Загружено {count} блоков контента!")
    except Exception as exc:
        logger.error("CSV import error: %s", exc)
        await message.answer(f"❌ Ошибка: {exc}")


async def _import_csv(session: AsyncSession, path: Path) -> int:
    """Parse CSV and upsert content_blocks."""
    from sqlalchemy import delete

    # Clear existing content
    await session.execute(delete(ContentBlock))

    count = 0
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                block = ContentBlock(
                    day=int(row["day"]),
                    block=int(row.get("block", 1)),
                    order=int(row["order"]),
                    type=ContentType(row["type"].strip().lower()),
                    content=row.get("content", "").strip() or None,
                    file_id=row.get("file_id", "").strip() or None,
                    caption=row.get("caption", "").strip() or None,
                    button_text=row.get("button_text", "").strip() or None,
                    button_callback=row.get("button_callback", "").strip() or None,
                    parse_mode=row.get("parse_mode", "HTML").strip(),
                    delay_seconds=int(row.get("delay_seconds", 0) or 0),
                )
                session.add(block)
                count += 1
            except (ValueError, KeyError) as exc:
                logger.warning("Skipping CSV row: %s — %s", row, exc)

    await session.commit()
    return count
