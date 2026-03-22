"""Admin commands: /admin, /sync, /test_send, /confirm_payment, /reset_user, /stats, /export, /broadcast."""

from __future__ import annotations

import csv
import io
import logging
from io import StringIO
from pathlib import Path

from aiogram import Router, types, Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
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
        "/grant <code>telegram_id</code> – Бесплатный доступ (для знакомых)\n"
        "/reset_user <code>telegram_id</code> – Полный сброс (квиз, оплата, прогресс)\n"
        "/stats – Статистика бота\n"
        "/export – Выгрузить данные квиза в CSV\n"
        "/broadcast <code>текст</code> – Рассылка всем прошедшим квиз\n"
        "/backup – Создать бэкап базы данных"
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

    # Quiz stats
    quiz_stats = await repo.get_quiz_stats(session)
    quiz_conv = (
        f"{quiz_stats['purchased']/quiz_stats['total']*100:.1f}%"
        if quiz_stats["total"] > 0
        else "0%"
    )

    # A/B test stats
    ab_a_total = (await session.execute(
        select(func.count(User.id)).where(User.ab_group == "A")
    )).scalar() or 0
    ab_b_total = (await session.execute(
        select(func.count(User.id)).where(User.ab_group == "B")
    )).scalar() or 0
    ab_a_paid = (await session.execute(
        select(func.count(User.id)).where(
            User.ab_group == "A", User.payment_status == PaymentStatus.paid
        )
    )).scalar() or 0
    ab_b_paid = (await session.execute(
        select(func.count(User.id)).where(
            User.ab_group == "B", User.payment_status == PaymentStatus.paid
        )
    )).scalar() or 0
    ab_a_conv = f"{ab_a_paid/ab_a_total*100:.1f}%" if ab_a_total > 0 else "—"
    ab_b_conv = f"{ab_b_paid/ab_b_total*100:.1f}%" if ab_b_total > 0 else "—"

    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👤 Всего: {total}\n"
        f"💰 Оплатили: {paid}\n"
        f"📈 Конверсия: {conversion}\n\n"
        "<b>Прохождение дней:</b>\n" +
        "\n".join(day_stats) +
        f"\n\n<b>Лиды:</b>\n"
        f"  🏠 АРЕНДА: {arenda}\n"
        f"  🤖 РОБОТ: {robot}\n\n"
        f"<b>Квиз:</b>\n"
        f"  📝 Прошли квиз: {quiz_stats['total']}\n"
        f"  🛡 Тип A (осторожный): {quiz_stats['type_a']}\n"
        f"  🚀 Тип B (готов): {quiz_stats['type_b']}\n"
        f"  📊 Тип C (инвестор): {quiz_stats['type_c']}\n"
        f"  💰 Купили после квиза: {quiz_stats['purchased']}\n"
        f"  📈 Конверсия квиз→покупка: {quiz_conv}\n\n"
        f"<b>A/B тест (квиз):</b>\n"
        f"  🅰️ Вариант A: {ab_a_total} чел → {ab_a_paid} покупок ({ab_a_conv})\n"
        f"  🅱️ Вариант B: {ab_b_total} чел → {ab_b_paid} покупок ({ab_b_conv})"
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
        "Спасибо за покупку программы «Графин»! 🎉\n\n"
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


@router.message(Command("export"))
async def cmd_export(message: types.Message, session: AsyncSession) -> None:
    """Export quiz users data as CSV file."""
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    users = await repo.get_all_quiz_users(session)
    if not users:
        await message.answer("📭 Нет пользователей, прошедших квиз.")
        return

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "telegram_id", "username", "first_name", "quiz_name",
        "user_type", "score", "utm_source", "purchased",
        "completed_at",
    ])
    for u in users:
        writer.writerow([
            u.telegram_id,
            u.username or "",
            u.first_name or "",
            u.quiz_name_entered or "",
            u.quiz_user_type or "",
            u.quiz_score or 0,
            u.utm_source or "",
            "yes" if u.payment_status == PaymentStatus.paid else "no",
            u.quiz_completed_at.strftime("%Y-%m-%d %H:%M") if u.quiz_completed_at else "",
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    doc = BufferedInputFile(csv_bytes, filename="quiz_users.csv")
    await message.answer_document(doc, caption=f"📊 Экспорт: {len(users)} пользователей")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, session: AsyncSession, bot: Bot) -> None:
    """Broadcast a message to all quiz completers."""
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    # Extract broadcast text (everything after /broadcast)
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer(
            "Использование: /broadcast <code>текст сообщения</code>\n\n"
            "Текст будет отправлен всем, кто прошёл квиз."
        )
        return

    users = await repo.get_all_quiz_users(session)
    if not users:
        await message.answer("📭 Нет пользователей для рассылки.")
        return

    await message.answer(f"📤 Начинаю рассылку {len(users)} пользователям...")

    sent = 0
    failed = 0
    blocked = 0

    for u in users:
        try:
            await bot.send_message(chat_id=u.telegram_id, text=text)
            sent += 1
        except TelegramForbiddenError:
            blocked += 1
            await repo.mark_user_blocked(session, u.telegram_id)
        except TelegramAPIError:
            failed += 1

        # Telegram rate limit: ~30 msg/sec
        import asyncio
        await asyncio.sleep(0.05)

    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено: {sent}\n"
        f"🚫 Заблокировали: {blocked}\n"
        f"❌ Ошибки: {failed}"
    )


@router.message(Command("grant"))
async def cmd_grant(
    message: types.Message, session: AsyncSession, bot: Bot
) -> None:
    """Grant free access to a user (for friends/testers)."""
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /grant <code>telegram_id</code>")
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

    if user.payment_status == PaymentStatus.paid:
        await message.answer(f"Пользователь {telegram_id} уже имеет доступ.")
        return

    await repo.confirm_payment(session, user.id, transaction_id="free_grant")

    # Notify user
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "━━━━━━━━━━━━━━━━━━━\n"
                "🎁 <b>ВАМ ОТКРЫТ ДОСТУП!</b>\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "Добро пожаловать в программу «Графин»! 🎉\n\n"
                "📚 Первый день программы начнётся через несколько секунд!"
            ),
        )
    except Exception as exc:
        logger.error("Failed to notify user %s: %s", telegram_id, exc)

    # Send Day 1
    import asyncio
    await asyncio.sleep(5)
    await send_full_day(bot, session, telegram_id, user.id, day=1)

    await message.answer(f"✅ Бесплатный доступ для {telegram_id} выдан, День 1 отправлен.")


@router.message(Command("reset_user"))
async def cmd_reset_user(
    message: types.Message, session: AsyncSession
) -> None:
    """Full reset of a user: payment, quiz results, and day progress."""
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "Использование: /reset_user <code>telegram_id</code>\n\n"
            "Сбрасывает: оплату, квиз, прогресс по дням."
        )
        return

    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный формат. Пример: /reset_user 123456789")
        return

    found = await repo.reset_user(session, telegram_id)
    if not found:
        await message.answer(f"Пользователь {telegram_id} не найден.")
        return

    await message.answer(
        f"✅ Пользователь <code>{telegram_id}</code> полностью сброшен.\n\n"
        f"- Оплата: нет\n"
        f"- Квиз: не пройден\n"
        f"- Прогресс: с нуля\n\n"
        f"Пользователь может снова пройти квиз и купить курс."
    )


@router.message(Command("backup"))
async def cmd_backup(message: types.Message, bot: Bot) -> None:
    """Manually trigger a database backup."""
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    await message.answer("📦 Создаю бэкап базы данных...")

    from bot.workers.backup import create_and_send_backup
    success = await create_and_send_backup(bot, send_to_chat_id=message.from_user.id)

    if success:
        await message.answer("✅ Бэкап создан и отправлен!")


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
                    content=(row.get("content") or "").strip() or None,
                    file_id=(row.get("file_id") or "").strip() or None,
                    caption=(row.get("caption") or "").strip() or None,
                    button_text=(row.get("button_text") or "").strip() or None,
                    button_callback=(row.get("button_callback") or "").strip() or None,
                    parse_mode=(row.get("parse_mode") or "HTML").strip(),
                    delay_seconds=int(row.get("delay_seconds", 0) or 0),
                )
                session.add(block)
                count += 1
            except (ValueError, KeyError) as exc:
                logger.warning("Skipping CSV row: %s — %s", row, exc)

    await session.commit()
    return count

