"""Database repository - async CRUD helpers used by handlers and services."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    ContentBlock,
    DayStatus,
    Lead,
    LeadType,
    Payment,
    PaymentStatus,
    User,
    UserProgress,
    UserStatus,
)


# ──────────────────────── Users ───────────────────────────────


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
) -> User:
    """Find user by telegram_id or create a new one with progress row."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
        )
        session.add(user)
        await session.flush()
        # Create progress row
        progress = UserProgress(user_id=user.id, current_day=1)
        session.add(progress)
        await session.commit()
        # Re-fetch to load progress
        await session.refresh(user, attribute_names=["progress"])
    else:
        # Update username/name if changed
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            changed = True
        if changed:
            await session.commit()

    return user


async def get_user_by_telegram_id(
    session: AsyncSession, telegram_id: int
) -> User | None:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def mark_user_blocked(session: AsyncSession, telegram_id: int) -> None:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.status = UserStatus.blocked
        await session.commit()


# ──────────────────────── Progress ────────────────────────────


async def get_progress(session: AsyncSession, user_id: int) -> UserProgress | None:
    stmt = select(UserProgress).where(UserProgress.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _day_status_attr(day: int) -> str:
    return f"day_{day}_status"


def _day_sent_at_attr(day: int) -> str:
    return f"day_{day}_sent_at"


def _day_completed_at_attr(day: int) -> str:
    return f"day_{day}_completed_at"


def _day_current_block_attr(day: int) -> str:
    return f"day_{day}_current_block"


def _day_reminder_sent_attr(day: int) -> str:
    return f"day_{day}_reminder_sent"


async def mark_day_sent(
    session: AsyncSession, user_id: int, day: int
) -> None:
    progress = await get_progress(session, user_id)
    if not progress:
        return
    # Don't overwrite if day is already completed (e.g. re-send via /test_send)
    current_status = getattr(progress, _day_status_attr(day))
    if current_status == DayStatus.completed:
        return
    setattr(progress, _day_status_attr(day), DayStatus.sent)
    setattr(progress, _day_sent_at_attr(day), datetime.now(timezone.utc))
    setattr(progress, _day_current_block_attr(day), 1)
    progress.current_day = day
    await session.commit()


async def update_current_block(
    session: AsyncSession, user_id: int, day: int, block: int
) -> None:
    progress = await get_progress(session, user_id)
    if not progress:
        return
    setattr(progress, _day_current_block_attr(day), block)
    await session.commit()


async def mark_day_completed(
    session: AsyncSession, user_id: int, day: int
) -> None:
    progress = await get_progress(session, user_id)
    if not progress:
        return
    setattr(progress, _day_status_attr(day), DayStatus.completed)
    setattr(progress, _day_completed_at_attr(day), datetime.now(timezone.utc))
    await session.commit()


async def mark_reminder_sent(
    session: AsyncSession, user_id: int, day: int
) -> None:
    progress = await get_progress(session, user_id)
    if not progress:
        return
    setattr(progress, _day_reminder_sent_attr(day), True)
    await session.commit()


# ──────────────────────── Content ─────────────────────────────


async def get_content_blocks(
    session: AsyncSession, day: int, block: int
) -> Sequence[ContentBlock]:
    """Return content blocks for given day/block, ordered by `order`."""
    stmt = (
        select(ContentBlock)
        .where(and_(ContentBlock.day == day, ContentBlock.block == block))
        .order_by(ContentBlock.order)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_max_block(session: AsyncSession, day: int) -> int:
    """Return the highest block number for a day."""
    from sqlalchemy import func as sa_func

    stmt = select(sa_func.max(ContentBlock.block)).where(ContentBlock.day == day)
    result = await session.execute(stmt)
    val = result.scalar()
    return val or 0


# ──────────────────────── Payments ────────────────────────────


async def create_payment(
    session: AsyncSession,
    user_id: int,
    amount: int = 0,
    payment_method: str | None = None,
) -> Payment:
    payment = Payment(
        user_id=user_id,
        amount=amount,
        payment_method=payment_method,
        status=PaymentStatus.pending,
    )
    session.add(payment)
    await session.commit()
    return payment


async def confirm_payment(
    session: AsyncSession,
    user_id: int,
    transaction_id: str | None = None,
) -> None:
    """Mark user as paid and update payment record."""
    user = await session.get(User, user_id)
    if not user:
        return
    user.payment_status = PaymentStatus.paid

    # Find pending payment
    stmt = (
        select(Payment)
        .where(and_(Payment.user_id == user_id, Payment.status == PaymentStatus.pending))
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    payment = result.scalar_one_or_none()
    if payment:
        payment.status = PaymentStatus.paid
        payment.paid_at = datetime.now(timezone.utc)
        if transaction_id:
            payment.transaction_id = transaction_id

    await session.commit()


# ──────────────────────── Leads ───────────────────────────────


async def save_lead(
    session: AsyncSession, user_id: int, lead_type: LeadType
) -> bool:
    """Save a lead. Returns True if new, False if already exists."""
    stmt = select(Lead).where(
        and_(Lead.user_id == user_id, Lead.lead_type == lead_type)
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return False
    session.add(Lead(user_id=user_id, lead_type=lead_type))
    await session.commit()
    return True


# ──────────────── Scheduler queries ───────────────────────────


async def get_users_needing_next_day(session: AsyncSession) -> list[dict]:
    """Find paid users who need the next day of content.

    Handles two cases:
    1. Day 1 auto-start: user is paid but day_1 is not_started yet
       (e.g. admin changed payment_status to 'paid' in NocoDB).
    2. Day N+1 progression: user completed day N and enough time has passed.
    """
    MINSK_TZ = ZoneInfo("Europe/Minsk")
    SEND_HOUR = 9  # отправка следующего дня не раньше 9:00 по Минску

    now_utc = datetime.now(timezone.utc)
    now_minsk = now_utc.astimezone(MINSK_TZ)
    today_start_minsk = now_minsk.replace(hour=0, minute=0, second=0, microsecond=0)
    results: list[dict] = []

    stmt = (
        select(User)
        .join(UserProgress, User.id == UserProgress.user_id)
        .where(
            and_(
                User.status == UserStatus.active,
                User.payment_status == PaymentStatus.paid,
            )
        )
    )
    rows = await session.execute(stmt)
    users = rows.scalars().all()

    for user in users:
        progress = await get_progress(session, user.id)
        if not progress:
            continue

        # --- Case 1: Day 1 auto-start for newly paid users ---
        day_1_status = getattr(progress, _day_status_attr(1))
        if day_1_status == DayStatus.not_started:
            results.append({"user": user, "day": 1, "reason": "paid_day1_autostart"})
            continue

        # --- Case 2: Day N -> Day N+1 progression ---
        for day in range(1, 5):
            next_day = day + 1
            status = getattr(progress, _day_status_attr(day))
            next_status = getattr(progress, _day_status_attr(next_day))
            completed_at = getattr(progress, _day_completed_at_attr(day))

            if status == DayStatus.completed and next_status == DayStatus.not_started:
                if user.force_next_day:
                    results.append({"user": user, "day": next_day, "reason": "force_next_day"})
                    break
                if completed_at:
                    completed_minsk = completed_at.replace(tzinfo=timezone.utc).astimezone(MINSK_TZ)
                    completed_day_start = completed_minsk.replace(hour=0, minute=0, second=0, microsecond=0)
                    if today_start_minsk > completed_day_start and now_minsk.hour >= SEND_HOUR:
                        results.append({"user": user, "day": next_day, "reason": "calendar_day"})
                        break

    return results


async def get_users_needing_reminder(session: AsyncSession) -> list[dict]:
    """Find users who need a 48h reminder for incomplete day tasks."""
    now = datetime.now(timezone.utc)
    results: list[dict] = []

    day_titles = {
        1: "Финансовый рентген",
        2: "Стратегия защиты денег",
        3: "Криптокошелёк",
        4: "Брокерский счёт",
        5: "Портфель + ускоритель",
    }

    stmt = (
        select(User)
        .join(UserProgress, User.id == UserProgress.user_id)
        .where(
            and_(
                User.status == UserStatus.active,
                User.payment_status == PaymentStatus.paid,
            )
        )
    )
    rows = await session.execute(stmt)
    users = rows.scalars().all()

    for user in users:
        progress = await get_progress(session, user.id)
        if not progress:
            continue

        for day in range(1, 6):
            status = getattr(progress, _day_status_attr(day))
            sent_at = getattr(progress, _day_sent_at_attr(day))
            reminder_sent = getattr(progress, _day_reminder_sent_attr(day))

            if status == DayStatus.sent and sent_at and not reminder_sent:
                hours_since = (now - sent_at).total_seconds() / 3600
                if hours_since >= 48:
                    results.append({
                        "user": user,
                        "day": day,
                        "title": day_titles.get(day, ""),
                    })
                    break  # one reminder per user per run

    return results


# ──────────────────────── Quiz ────────────────────────────────


async def save_quiz_result(
    session: AsyncSession,
    telegram_id: int,
    answers: dict,
    score: int,
    user_type: str,
    name: str,
    ab_group: str | None = None,
) -> User | None:
    """Save quiz results for a user."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None
    user.quiz_answers = answers
    user.quiz_score = score
    user.quiz_user_type = user_type
    user.quiz_name_entered = name
    user.quiz_completed_at = datetime.now(timezone.utc)
    user.quiz_followup_step = 0
    user.quiz_followup_last_at = datetime.now(timezone.utc)
    if ab_group:
        user.ab_group = ab_group
    await session.commit()
    return user


async def get_quiz_followup_users(session: AsyncSession) -> list[User]:
    """Find users who completed the quiz but haven't paid - for follow-up chain."""
    stmt = (
        select(User)
        .where(
            and_(
                User.quiz_completed_at.isnot(None),
                User.payment_status != PaymentStatus.paid,
                User.quiz_followup_step < 3,
                User.status == UserStatus.active,
            )
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_followup_step(
    session: AsyncSession, user_id: int, step: int
) -> None:
    """Update follow-up chain step for a user."""
    user = await session.get(User, user_id)
    if not user:
        return
    user.quiz_followup_step = step
    user.quiz_followup_last_at = datetime.now(timezone.utc)
    await session.commit()


async def get_quiz_stats(session: AsyncSession) -> dict:
    """Get quiz statistics for /stats command."""
    from sqlalchemy import func as sa_func

    total_quiz = (await session.execute(
        select(sa_func.count(User.id)).where(User.quiz_completed_at.isnot(None))
    )).scalar() or 0

    type_a = (await session.execute(
        select(sa_func.count(User.id)).where(
            and_(User.quiz_completed_at.isnot(None), User.quiz_user_type == "A")
        )
    )).scalar() or 0

    type_b = (await session.execute(
        select(sa_func.count(User.id)).where(
            and_(User.quiz_completed_at.isnot(None), User.quiz_user_type == "B")
        )
    )).scalar() or 0

    type_c = (await session.execute(
        select(sa_func.count(User.id)).where(
            and_(User.quiz_completed_at.isnot(None), User.quiz_user_type == "C")
        )
    )).scalar() or 0

    quiz_purchased = (await session.execute(
        select(sa_func.count(User.id)).where(
            and_(
                User.quiz_completed_at.isnot(None),
                User.payment_status == PaymentStatus.paid,
            )
        )
    )).scalar() or 0

    return {
        "total": total_quiz,
        "type_a": type_a,
        "type_b": type_b,
        "type_c": type_c,
        "purchased": quiz_purchased,
    }


async def get_all_quiz_users(session: AsyncSession) -> Sequence[User]:
    """Get all users who completed the quiz - for /export and /broadcast."""
    stmt = (
        select(User)
        .where(User.quiz_completed_at.isnot(None))
        .order_by(User.quiz_completed_at.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def mark_user_blocked(session: AsyncSession, telegram_id: int) -> None:
    """Mark user as blocked (they blocked the bot)."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.status = UserStatus.blocked
        await session.commit()


async def reset_user(session: AsyncSession, telegram_id: int) -> bool:
    """Full reset: clears payment, quiz results, and all day progress.
    Returns True if user was found, False otherwise."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return False

    # Reset payment
    user.payment_status = PaymentStatus.none
    user.status = UserStatus.active

    # Reset quiz
    user.quiz_answers = None
    user.quiz_score = None
    user.quiz_user_type = None
    user.quiz_name_entered = None
    user.quiz_completed_at = None
    user.quiz_followup_step = 0
    user.quiz_followup_last_at = None
    user.ab_group = None

    await session.commit()

    # Reset progress
    progress = await get_progress(session, user.id)
    if progress:
        progress.current_day = 1
        for day in range(1, 6):
            setattr(progress, f"day_{day}_status", DayStatus.not_started)
            setattr(progress, f"day_{day}_current_block", 0)
            setattr(progress, f"day_{day}_sent_at", None)
            setattr(progress, f"day_{day}_completed_at", None)
            setattr(progress, f"day_{day}_reminder_sent", False)
        await session.commit()

    return True

