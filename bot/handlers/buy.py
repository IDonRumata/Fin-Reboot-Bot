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
        "«Графин».\n\n"
        "<b>2. Предмет оферты</b>\n"
        "▸ Курс предоставляется в формате Telegram-бота\n"
        "▸ Доступ – 5 дней с момента активации\n"
        "▸ Стоимость – <b>45 BYN</b>\n\n"
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
        "Курс «Графин» - информационно-образовательный продукт.\n"
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

    # Create pending payment
    await repo.create_payment(session, user.id, amount=4500, payment_method="bepaid")

    # Try to create dynamic bePaid checkout with tracking_id
    payment_url = await _create_bepaid_checkout(callback.from_user.id)

    # Show both payment options: bePaid online + card transfer
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="💳 Оплатить онлайн (bePaid)",
                url=payment_url,
            )],
            [InlineKeyboardButton(
                text="💵 Перевод на карту",
                callback_data="pay_by_card",
            )],
            [InlineKeyboardButton(text="🔙 Меню", callback_data="menu")],
        ]
    )
    auto_note = ""
    if payment_url != settings.bepaid_payment_url:
        auto_note = "\n✨ После оплаты курс активируется <b>автоматически</b>!"

    text = (
        "💳 <b>Открытие доступа</b>\n\n"
        "Стоимость: <b>45 BYN</b>\n\n"
        "Выберите удобный способ оплаты:\n\n"
        f"🔹 <b>Онлайн (bePaid)</b> – моментальная автоматическая активация{auto_note}\n"
        "🔹 <b>Перевод на карту</b> – ручная проверка администратором"
    )

    if callback.message:
        await callback.message.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]


async def _create_bepaid_checkout(telegram_id: int) -> str:
    """Create a bePaid checkout session with tracking_id for auto-payment.
    
    Returns the payment URL. Falls back to static URL on error.
    """
    if not settings.bepaid_shop_id or not settings.bepaid_secret_key:
        logger.warning("bePaid credentials not configured, using static URL")
        return settings.bepaid_payment_url

    import aiohttp
    import base64

    auth = base64.b64encode(
        f"{settings.bepaid_shop_id}:{settings.bepaid_secret_key}".encode()
    ).decode()

    payload = {
        "checkout": {
            "test": False,
            "transaction_type": "payment",
            "attempts": 3,
            "settings": {
                "success_url": "https://t.me/fin_reboot_bot?start=payment_success",
                "decline_url": "https://t.me/fin_reboot_bot?start=payment_fail",
                "fail_url": "https://t.me/fin_reboot_bot?start=payment_fail",
                "notification_url": settings.bepaid_notification_url or f"http://185.229.251.166:{settings.webhook_port}/webhook/bepaid",
                "language": "ru",
                "customer_fields": {
                    "visible": ["email"],
                    "read_only": [],
                },
            },
            "order": {
                "currency": "BYN",
                "amount": 4500,  # 45.00 BYN in cents
                "description": f"Курс «Графин» (ID: {telegram_id})",
                "tracking_id": str(telegram_id),
            },
        }
    }

    try:
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                settings.bepaid_checkout_url,
                json=payload,
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200 or resp.status == 201:
                    data = await resp.json()
                    checkout_url = data.get("checkout", {}).get("redirect_url", "")
                    if checkout_url:
                        logger.info("Created bePaid checkout for user %s: %s", telegram_id, checkout_url[:50])
                        return checkout_url
                    else:
                        logger.error("bePaid response missing redirect_url: %s", data)
                else:
                    body = await resp.text()
                    logger.error("bePaid checkout API error %s: %s", resp.status, body[:300])
    except Exception as exc:
        logger.error("Failed to create bePaid checkout: %s", exc)

    # Fallback to static URL
    return settings.bepaid_payment_url


@router.callback_query(F.data == "pay_by_card")
async def cb_pay_by_card(
    callback: types.CallbackQuery,
) -> None:
    """Show card transfer instructions."""
    await callback.answer()
    text = (
        "💵 <b>Перевод на карту</b>\n\n"
        "Стоимость: <b>45 BYN</b>\n\n"
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
