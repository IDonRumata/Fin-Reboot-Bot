"""Payment webhook handler - authenticated bePaid notification processing.

Security model (see SECURITY_FIX notes):
  The /webhook/bepaid endpoint is publicly reachable, so it MUST authenticate
  every incoming request before granting course access. We do this with a shared
  secret that WE control on both ends:
    - the secret is stored in BEPAID_WEBHOOK_SECRET (env);
    - it is appended to the Notification URL configured in the bePaid dashboard
      (e.g. .../webhook/bepaid?token=<secret>), so genuine bePaid calls carry it;
    - forged requests that lack the correct secret are rejected and never activate
      a user.
  In addition we verify the paid amount and status, and activation is idempotent.

  This shared-secret gate cannot false-reject legitimate bePaid notifications
  (bePaid calls exactly the URL we register), so it is safe for production.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging

from aiohttp import web
from aiogram import Bot

from bot.core.config import settings
from bot.database import repositories as repo
from bot.database.engine import async_session
from bot.services.content_sender import send_full_day

logger = logging.getLogger(__name__)


def _const_eq(a: str, b: str) -> bool:
    """Constant-time string comparison (avoids timing side-channels)."""
    return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


def _verify_webhook_secret(request: web.Request, expected: str) -> bool:
    """Authenticate a payment webhook via shared secret.

    Accepts the secret from either the `token` query parameter or the
    `X-Webhook-Token` header. Fails closed when no secret is configured.
    """
    if not expected:
        # Misconfiguration: refuse to auto-activate until a secret is set.
        logger.critical(
            "Webhook secret is not configured (BEPAID_WEBHOOK_SECRET empty) - "
            "rejecting webhook. Set it in .env and in the bePaid dashboard URL."
        )
        return False
    provided = request.query.get("token", "") or request.headers.get("X-Webhook-Token", "")
    return _const_eq(provided, expected)


async def _alert_admins(bot: Bot, text: str) -> None:
    """Best-effort Telegram alert to admins (never raises)."""
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except Exception:  # noqa: BLE001 - alerting must not break the request
            pass


async def handle_bepaid_webhook(request: web.Request) -> web.Response:
    """Process incoming bePaid payment notification (authenticated)."""
    bot: Bot = request.app["bot"]

    # ── 1. Read & size-limit body ──
    try:
        body = await request.read()
        if len(body) > 1_048_576:
            logger.warning("Webhook payload too large: %d bytes", len(body))
            return web.Response(status=413, text="Payload too large")
        data = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse webhook body: %s", exc)
        return web.Response(status=400, text="Bad request")

    # ── 2. Authenticate BEFORE doing anything else ──
    if not _verify_webhook_secret(request, settings.bepaid_webhook_secret):
        logger.warning(
            "Rejected unauthenticated bePaid webhook from %s",
            request.headers.get("X-Forwarded-For", request.remote),
        )
        await _alert_admins(
            bot,
            "⚠️ Отклонён неавторизованный платёжный вебхук (неверный/отсутствует "
            "секрет). Если это была реальная оплата — подтвердите вручную "
            "командой /confirm_payment.",
        )
        # Do not reveal auth details to the caller.
        return web.Response(status=401, text="Unauthorized")

    # ── 3. Extract transaction info (supports both bePaid payload shapes) ──
    transaction = data.get("transaction", {}) or {}
    order = data.get("order", {}) or transaction.get("order", {}) or {}

    status = (transaction.get("status") or data.get("status") or "").lower()
    transaction_id = str(transaction.get("id", "") or transaction.get("uid", "") or data.get("token", ""))
    amount = transaction.get("amount") or order.get("amount") or 0
    currency = (transaction.get("currency") or order.get("currency") or "").upper()

    tracking_id = (
        str(transaction.get("tracking_id", ""))
        or str(order.get("tracking_id", ""))
        or str(data.get("tracking_id", ""))
    )
    telegram_id = _extract_telegram_id(tracking_id, data)

    # Log without dumping full PII-bearing body.
    logger.info(
        "bePaid webhook OK: status=%s amount=%s %s tg=%s txn=%s",
        status, amount, currency, telegram_id, transaction_id,
    )

    if not telegram_id:
        logger.warning("Webhook: could not determine telegram_id")
        return web.Response(status=200, text="OK (no telegram_id)")

    # ── 4. Act on status ──
    if status in ("successful", "success", "captured"):
        # Verify amount matches the course price (reject under-payments / tampering).
        try:
            amount_int = int(amount)
        except (TypeError, ValueError):
            amount_int = 0
        if amount_int and settings.bepaid_expected_amount and amount_int != settings.bepaid_expected_amount:
            logger.warning(
                "Amount mismatch tg=%s: got %s expected %s - not activating",
                telegram_id, amount_int, settings.bepaid_expected_amount,
            )
            await _alert_admins(
                bot,
                f"⚠️ Оплата с неверной суммой от {telegram_id}: {amount_int} "
                f"(ожидалось {settings.bepaid_expected_amount}). Проверьте вручную.",
            )
            return web.Response(status=200, text="OK (amount mismatch)")

        logger.info("Payment successful for telegram_id=%s, txn=%s", telegram_id, transaction_id)
        await _activate_user(bot, telegram_id, transaction_id)
        return web.Response(status=200, text="OK")

    logger.info("Payment status '%s' for telegram_id=%s - ignoring", status, telegram_id)
    return web.Response(status=200, text="OK")


def _extract_telegram_id(tracking_id: str, data: dict) -> int | None:
    """Try to extract telegram_id from webhook fields."""
    if tracking_id and tracking_id.isdigit():
        return int(tracking_id)

    customer = data.get("customer", {}) or data.get("transaction", {}).get("customer", {})
    email = customer.get("email", "")
    if email and "@tg." in email:
        try:
            return int(email.split("@")[0])
        except ValueError:
            pass
    return None


async def _activate_user(bot: Bot, telegram_id: int, transaction_id: str) -> None:
    """Confirm payment and send Day 1 content (idempotent)."""
    async with async_session() as session:
        user = await repo.get_user_by_telegram_id(session, telegram_id)
        if not user:
            logger.warning("Webhook: user %s not found in DB", telegram_id)
            await _alert_admins(
                bot,
                f"⚠️ Оплата от {telegram_id}, но пользователь не найден в БД. "
                f"Проверьте вручную.",
            )
            return

        from bot.database.models import PaymentStatus
        if user.payment_status == PaymentStatus.paid:
            logger.info("User %s already paid - skipping", telegram_id)
            return

        await repo.confirm_payment(session, user.id, transaction_id=transaction_id)
        logger.info("Payment confirmed for user %s", telegram_id)

        confirm_text = (
            "━━━━━━━━━━━━━━━━━━━\n"
            "✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "Спасибо за покупку «Графина»! 🎉\n\n"
            '👉 <a href="' + settings.participants_chat_url + '">Чат участников</a> '
            "— присоединяйся для общения и обратной связи\n\n"
            "📚 Первый день программы начнётся через несколько секунд!"
        )
        checklist_text = (
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎁 <b>БОНУС: Подготовься к первой инвестиции</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "7 вопросов, которые стоит задать себе до начала:\n\n"
            "1️⃣ <b>Сколько могу откладывать ежемесячно?</b>\n"
            "Реальная сумма — не «хотелось бы». Даже 50 BYN — это старт.\n\n"
            "2️⃣ <b>Есть ли подушка безопасности?</b>\n"
            "3–6 месячных расходов в резерве. Инвестировать без подушки — рисковать необходимыми деньгами.\n\n"
            "3️⃣ <b>Какая моя финансовая цель?</b>\n"
            "Конкретная сумма и срок. «100 000 BYN через 10 лет» — план. «Хочу больше денег» — мечта.\n\n"
            "4️⃣ <b>Готов(а) ли я к просадкам?</b>\n"
            "Инвестиции временно падают. Продашь в панике или подождёшь? Честный ответ важен.\n\n"
            "5️⃣ <b>На какой срок инвестирую?</b>\n"
            "До 3 лет — инструменты одни, от 5 лет — другие. Срок определяет стратегию.\n\n"
            "6️⃣ <b>Есть ли долги с высоким %?</b>\n"
            "Кредит под 20% — сначала гаси его. Инвестиции редко дают больше стоимости долга.\n\n"
            "7️⃣ <b>Зачем мне это? Мой личный «почему»</b>\n"
            "Запиши одним предложением. В трудный момент именно это не даст бросить.\n\n"
            "Ответы на эти вопросы разберём в курсе. Поехали! 🚀"
        )

        try:
            await bot.send_message(chat_id=telegram_id, text=confirm_text, disable_web_page_preview=True)
            await asyncio.sleep(3)
            await bot.send_message(chat_id=telegram_id, text=checklist_text)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to notify user %s: %s", telegram_id, exc)

        await asyncio.sleep(5)
        await send_full_day(bot, session, telegram_id, user.id, day=1)
        logger.info("Day 1 sent to user %s", telegram_id)


async def handle_expresspay_webhook(request: web.Request) -> web.Response:
    """Process Express-pay payment notification (authenticated, constant-time).

    NOTE: not routed by default (bePaid is the active provider). If enabled,
    EXPRESSPAY_WEBHOOK_TOKEN must be set and configured in the Express-pay panel.
    """
    bot: Bot = request.app["bot"]
    try:
        body = await request.read()
        if len(body) > 1_048_576:
            return web.Response(status=413, text="Payload too large")
        data = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        logger.error("Express-pay webhook parse error: %s", exc)
        return web.Response(status=400, text="Bad request")

    # Require and verify token (constant-time). Fail closed.
    expected = settings.expresspay_webhook_token
    if not expected:
        logger.critical("Express-pay webhook token not configured - rejecting")
        return web.Response(status=401, text="Unauthorized")
    token = request.headers.get("X-Api-Key", "") or request.query.get("token", "")
    if not _const_eq(token, expected):
        logger.warning("Express-pay webhook: invalid token")
        return web.Response(status=401, text="Unauthorized")

    status = str(data.get("Status", data.get("status", ""))).lower()
    account_no = str(data.get("AccountNo", data.get("accountNo", "")))
    invoice_no = str(data.get("InvoiceNo", data.get("invoiceNo", data.get("id", ""))))

    if not account_no or not account_no.isdigit():
        logger.warning("Express-pay webhook: missing/invalid AccountNo")
        return web.Response(status=200, text="OK")

    telegram_id = int(account_no)
    if status in ("success", "оплачен", "paid", "1"):
        logger.info("Express-pay success tg=%s invoice=%s", telegram_id, invoice_no)
        await _activate_user(bot, telegram_id, f"expresspay_{invoice_no}")
    else:
        logger.info("Express-pay status '%s' tg=%s - ignoring", status, telegram_id)

    return web.Response(status=200, text="OK")


async def health_check(request: web.Request) -> web.Response:
    return web.Response(text="OK")


def create_webhook_app(bot: Bot) -> web.Application:
    """Create aiohttp web app for payment webhooks."""
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/webhook/bepaid", handle_bepaid_webhook)
    app.router.add_get("/health", health_check)
    # Express-pay handler intentionally not routed (bePaid is the active provider).
    # To enable: app.router.add_post("/webhook/expresspay", handle_expresspay_webhook)
    return app
