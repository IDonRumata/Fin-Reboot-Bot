"""SQLAlchemy models for ALL database tables."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ──────────────────────────── Base ────────────────────────────


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


# ──────────────────────────── Enums ───────────────────────────


class UserStatus(str, enum.Enum):
    active = "active"
    blocked = "blocked"


class PaymentStatus(str, enum.Enum):
    none = "none"
    pending = "pending"
    paid = "paid"
    failed = "failed"


class DayStatus(str, enum.Enum):
    not_started = "not_started"
    sent = "sent"
    completed = "completed"


class ContentType(str, enum.Enum):
    text = "text"
    text_with_button = "text_with_button"
    text_with_webapp = "text_with_webapp"
    photo = "photo"
    video = "video"
    video_note = "video_note"
    voice = "voice"


class LeadType(str, enum.Enum):
    arenda = "arenda"
    robot = "robot"


# ──────────────────────────── Users ───────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), default=UserStatus.active, server_default="active"
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.none, server_default="none"
    )

    # UTM tracking
    utm_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(255), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Testing
    force_next_day: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Quiz fields
    quiz_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quiz_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quiz_user_type: Mapped[str | None] = mapped_column(String(1), nullable=True)
    quiz_name_entered: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quiz_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quiz_followup_step: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    quiz_followup_last_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    progress: Mapped[UserProgress | None] = relationship(
        "UserProgress", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    payments: Mapped[list[Payment]] = relationship(
        "Payment", back_populates="user", cascade="all, delete-orphan"
    )
    leads: Mapped[list[Lead]] = relationship(
        "Lead", back_populates="user", cascade="all, delete-orphan"
    )


# ──────────────────────── User Progress ───────────────────────


class UserProgress(Base):
    __tablename__ = "user_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    current_day: Mapped[int] = mapped_column(Integer, default=1)

    # Day 1
    day_1_status: Mapped[DayStatus] = mapped_column(
        Enum(DayStatus), default=DayStatus.not_started, server_default="not_started"
    )
    day_1_current_block: Mapped[int] = mapped_column(Integer, default=0)
    day_1_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_1_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_1_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Day 2
    day_2_status: Mapped[DayStatus] = mapped_column(
        Enum(DayStatus), default=DayStatus.not_started, server_default="not_started"
    )
    day_2_current_block: Mapped[int] = mapped_column(Integer, default=0)
    day_2_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_2_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_2_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Day 3
    day_3_status: Mapped[DayStatus] = mapped_column(
        Enum(DayStatus), default=DayStatus.not_started, server_default="not_started"
    )
    day_3_current_block: Mapped[int] = mapped_column(Integer, default=0)
    day_3_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_3_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_3_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Day 4
    day_4_status: Mapped[DayStatus] = mapped_column(
        Enum(DayStatus), default=DayStatus.not_started, server_default="not_started"
    )
    day_4_current_block: Mapped[int] = mapped_column(Integer, default=0)
    day_4_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_4_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_4_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Day 5
    day_5_status: Mapped[DayStatus] = mapped_column(
        Enum(DayStatus), default=DayStatus.not_started, server_default="not_started"
    )
    day_5_current_block: Mapped[int] = mapped_column(Integer, default=0)
    day_5_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_5_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_5_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    user: Mapped[User] = relationship("User", back_populates="progress")


# ─────────────────────── Content Blocks ───────────────────────


class ContentBlock(Base):
    __tablename__ = "content_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    block: Mapped[int] = mapped_column(Integer, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    type: Mapped[ContentType] = mapped_column(Enum(ContentType), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    button_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    button_callback: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parse_mode: Mapped[str] = mapped_column(String(10), default="HTML")
    delay_seconds: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("day", "block", "order", name="uq_day_block_order"),
    )


# ──────────────────────── Payments ────────────────────────────


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)  # in cents
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="payments")


# ──────────────────────── Leads ───────────────────────────────


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lead_type: Mapped[LeadType] = mapped_column(Enum(LeadType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="leads")

    __table_args__ = (
        UniqueConstraint("user_id", "lead_type", name="uq_user_lead_type"),
    )
