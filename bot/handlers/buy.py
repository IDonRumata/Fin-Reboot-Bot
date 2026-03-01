"""Buy flow: oferta → accept → payment instructions / bePaid link."""

from __future__ import annotations

import logging

from aiogram import Router, types, F, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import settings
from bot.database import repositories as repo
from bot.database.models import PaymentStatus

logger = logging.getLogger(__name__)
router = Router(name="buy")


@router.callback_query(F.data == "buy")
async def cb_buy(callback: types.CallbackQuery) -> None:
    await callback.answer()

    oferta_text = (
        "━━━━━━━━━━━━━━━━━━━\n"
        "📜 <b>Публичная оферта</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>1. Общие положения</b>\n"
        "Настоящий документ является официальным предложением (публичной офертой) "
        "на оказание информационно-образовательных услуг в рамках курса "
        "«Финансовая перезагрузка».\n\n"
        "<b>2. Предмет оферты</b>\n"
        "▸ Курс предоставляется в формате Telegram-бота\n"
        "▸ Доступ – 5 дней с момента активации\n"
        "▸ Стоимость – <b>15 BYN</b>\n\n"
        "<b>3. Условия</b>\n"
        "▸ Материалы содержат личный опыт автора и не являются "
        "индивидуальными инвестиционными рекомендациями\n"
        "▸ Оплата является подтверждением согласия с условиями оферты\n\n"
        '📎 <a href="https://docs.google.com/document/d/1yMMQiBvAoAIScFU9XvMXRJVnyoqpRb7FqCCh9w41NwI">'
        "Полный текст оферты</a>\n\n"
        "Нажимая «Принимаю условия», вы подтверждаете согласие с офертой."
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принимаю условия", callback_data="accept_oferta")],
            [InlineKeyboardButton(text="🔙 Меню", callback_data="menu")],
        ]
    )
    if callback.message:
        await callback.message.answer(oferta_text, reply_markup=keyboard, disable_web_page_preview=True)  # type: ignore[union-attr]


@router.callback_query(F.data == "oferta")
async def cb_oferta(callback: types.CallbackQuery) -> None:
    """Just show oferta text with back button."""
    await callback.answer()
    text = (
        "📜 <b>Публичная оферта</b>\n\n"
        "Курс «Финансовая перезагрузка» – информационно-образовательный продукт.\n"
        "Автор делится личным опытом и не является лицензированным финансовым консультантом.\n\n"
        '📎 <a href="https://docs.google.com/document/d/1yMMQiBvAoAIScFU9XvMXRJVnyoqpRb7FqCCh9w41NwI">'
        "Читать полный текст оферты</a>"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Меню", callback_data="menu")],
        ]
    )
    if callback.message:
        await callback.message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)  # type: ignore[union-attr]


@router.callback_query(F.data == "accept_oferta")
async def cb_accept_oferta(
    callback: types.CallbackQuery,
    session: AsyncSession,
    bot: Bot,
) -> None:
    await callback.answer("Загружаю...", cache_time=5)

    if not callback.from_user:
        return

    user = await repo.get_user_by_telegram_id(session, callback.from_user.id)
    if not user:
        return

    # If already paid — tell them
    if user.payment_status == PaymentStatus.paid:
        if callback.message:
            await callback.message.answer(  # type: ignore[union-attr]
                "✅ Вы уже оплатили курс! Используйте /progress для проверки прогресса."
            )
        return

    # Show both payment options: bePaid online + card transfer
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="💳 Оплатить онлайн (bePaid)",
                url=settings.bepaid_payment_url,
            )],
            [InlineKeyboardButton(
                text="💵 Перевод на карту",
                callback_data="pay_by_card",
            )],
            [InlineKeyboardButton(text="🔙 Меню", callback_data="menu")],
        ]
    )
    text = (
        "💳 <b>Оплата курса</b>\n\n"
        "Стоимость: <b>15 BYN</b>\n\n"
        "Выберите удобный способ оплаты:\n\n"
        "🔹 <b>Онлайн (bePaid)</b> – моментальная автоматическая активация\n"
        "🔹 <b>Перевод на карту</b> – ручная проверка администратором"
    )

    # Create pending payment
    await repo.create_payment(session, user.id, amount=1500, payment_method="bepaid")

    if callback.message:
        await callback.message.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]


@router.callback_query(F.data == "pay_by_card")
async def cb_pay_by_card(
    callback: types.CallbackQuery,
) -> None:
    """Show card transfer instructions."""
    await callback.answer()
    text = (
        "💵 <b>Перевод на карту</b>\n\n"
        "Стоимость: <b>15 BYN</b>\n\n"
        "Переведите на карту:\n"
        "<code>4601 2202 6102 6578</code>\n"
        "Получатель: Дементьева Марина\n\n"
        "После перевода нажмите кнопку ниже.\n"
        f"Если возникнут вопросы - {settings.support_username}"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data="payment_sent")],
            [InlineKeyboardButton(text="🔙 Меню", callback_data="menu")],
        ]
    )
    if callback.message:
        await callback.message.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]


@router.callback_query(F.data == "payment_sent")
async def cb_payment_sent(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
        "📩 <b>Спасибо!</b>\n\n"
        "Мы получим уведомление об оплате. "
        f"Если оплата не подтвердится автоматически - напишите {settings.support_username}\n\n"
        "Обычно активация занимает несколько минут."
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Меню", callback_data="menu")],
        ]
    )
    if callback.message:
        await callback.message.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]
