"""bePaid webhook handler — automatic payment verification.

Listens for POST notifications from bePaid when a payment succeeds.
Automatically confirms payment and triggers Day 1 content delivery.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging

from aiohttp import web
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import settings
from bot.database import repositories as repo
from bot.database.engine import async_session
from bot.services.content_sender import send_full_day

logger = logging.getLogger(__name__)


async def handle_bepaid_webhook(request: web.Request) -> web.Response:
    """Process incoming bePaid payment notification.

    bePaid sends a POST with JSON body containing transaction details.
    We verify the payment status and activate the user's course.
    """
    try:
        body = await request.read()
        # Reject oversized payloads (max 1 MB)
        if len(body) > 1_048_576:
            logger.warning("Webhook payload too large: %d bytes", len(body))
            return web.Response(status=413, text="Payload too large")
        data = json.loads(body)
    except Exception as exc:
        logger.error("Failed to parse webhook body: %s", exc)
        return web.Response(status=400, text="Bad request")

    logger.info("bePaid webhook received: %s", json.dumps(data, ensure_ascii=False)[:500])

    # ── Verify Basic Auth (bePaid sends Authorization: Basic base64(shop_id:secret_key)) ──
    if settings.bepaid_shop_id and settings.bepaid_secret_key:
        import base64
        auth_header = request.headers.get("Authorization", "")
        expected_credentials = base64.b64encode(
            f"{settings.bepaid_shop_id}:{settings.bepaid_secret_key}".encode()
        ).decode()
        expected_auth = f"Basic {expected_credentials}"
        if auth_header != expected_auth:
            logger.warning("Webhook auth failed. Header: %s", auth_header[:30] if auth_header else "(empty)")
            return web.Response(status=401, text="Unauthorized")

    # ── Extract transaction info ──
    transaction = data.get("transaction", {})
    status = transaction.get("status", "")
    tracking_id = transaction.get("tracking_id", "")
    transaction_id = str(transaction.get("id", "") or transaction.get("uid", ""))

    # Also check top-level for different bePaid formats
    if not status:
        status = data.get("status", "")
    if not tracking_id:
        tracking_id = data.get("tracking_id", "")
        # For product payments, tracking_id may be in order
        order = data.get("order", {}) or transaction.get("order", {})
        if not tracking_id:
            tracking_id = str(order.get("tracking_id", ""))

    # Try to extract telegram_id from tracking_id or description
    telegram_id = _extract_telegram_id(tracking_id, data)

    if not telegram_id:
        logger.warning("Could not determine telegram_id from webhook data")
        return web.Response(status=200, text="OK (no telegram_id)")

    # ── Process based on status ──
    if status in ("successful", "success", "captured"):
        logger.info("Payment successful for telegram_id=%s, txn=%s", telegram_id, transaction_id)
        bot: Bot = request.app["bot"]
        await _activate_user(bot, telegram_id, transaction_id)
        return web.Response(status=200, text="OK")

    elif status in ("failed", "declined", "void", "expired"):
        logger.info("Payment %s for telegram_id=%s", status, telegram_id)
        return web.Response(status=200, text="OK")

    else:
        logger.info("Payment status '%s' for telegram_id=%s — ignoring", status, telegram_id)
        return web.Response(status=200, text="OK")


def _extract_telegram_id(tracking_id: str, data: dict) -> int | None:
    """Try to extract telegram_id from various webhook fields."""
    # Direct tracking_id
    if tracking_id and tracking_id.isdigit():
        return int(tracking_id)

    # Check description for telegram_id pattern
    description = ""
    order = data.get("order", {}) or data.get("transaction", {}).get("order", {})
    if order:
        description = order.get("description", "")

    # Try email or other identifiers
    customer = data.get("customer", {}) or data.get("transaction", {}).get("customer", {})
    email = customer.get("email", "")
    # If email contains telegram_id (custom setup)
    if email and "@tg." in email:
        try:
            return int(email.split("@")[0])
        except ValueError:
            pass

    return None


async def _activate_user(bot: Bot, telegram_id: int, transaction_id: str) -> None:
    """Confirm payment and send Day 1 content."""
    async with async_session() as session:
        user = await repo.get_user_by_telegram_id(session, telegram_id)
        if not user:
            logger.warning("Webhook: user %s not found in DB", telegram_id)
            return

        # Check if already paid (idempotency)
        from bot.database.models import PaymentStatus
        if user.payment_status == PaymentStatus.paid:
            logger.info("User %s already paid — skipping", telegram_id)
            return

        # Confirm payment
        await repo.confirm_payment(session, user.id, transaction_id=transaction_id)
        logger.info("Payment confirmed for user %s", telegram_id)

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

        # Wait a bit and send Day 1
        await asyncio.sleep(5)
        await send_full_day(bot, session, telegram_id, user.id, day=1)
        logger.info("Day 1 sent to user %s", telegram_id)


async def health_check(request: web.Request) -> web.Response:
    """Simple health check endpoint."""
    return web.Response(text="OK")


def create_webhook_app(bot: Bot) -> web.Application:
    """Create aiohttp web app for bePaid webhooks."""
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/webhook/bepaid", handle_bepaid_webhook)
    app.router.add_get("/health", health_check)
    return app
