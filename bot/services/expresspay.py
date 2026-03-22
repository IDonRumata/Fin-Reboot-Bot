"""Express-pay.by API client — invoice creation and webhook handling.

Creates payment invoices via Express-pay API.
When client pays, Express-pay sends webhook → bot activates user access.

API docs: https://api.express-pay.by/v1/
Auth: Token passed as query parameter (not Bearer header).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiohttp

from bot.core.config import settings

logger = logging.getLogger(__name__)

EXPRESSPAY_API_URL = "https://api.express-pay.by/v1/"


async def create_invoice(telegram_id: int) -> str | None:
    """Create Express-pay invoice and return payment URL.

    Returns payment URL string on success, None on failure.
    """
    if not settings.expresspay_api_key or not settings.expresspay_service_id:
        logger.warning("Express-pay not configured (missing api_key or service_id)")
        return None

    # Invoice expires in 24 hours
    expiration = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    # Express-pay uses Token as query param + PascalCase field names
    params = {
        "Token": settings.expresspay_api_key,
        "ServiceId": settings.expresspay_service_id,
        "AccountNo": str(telegram_id),
        "Amount": "45.00",
        "Currency": "BYN",
        "Expiration": expiration,
        "ReturnUrl": f"https://t.me/{settings.bot_username}?start=payment_success",
        "FailUrl": f"https://t.me/{settings.bot_username}?start=payment_fail",
        "Language": "ru",
        "Info": f"Графин - база знаний по инвестициям (ID: {telegram_id})",
    }

    try:
        async with aiohttp.ClientSession() as http:
            # Try POST /webpayments (primary Express-pay endpoint)
            async with http.post(
                f"{EXPRESSPAY_API_URL}webpayments",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                body = await resp.text()
                logger.info(
                    "Express-pay /webpayments response for %s: status=%s body=%s",
                    telegram_id,
                    resp.status,
                    body[:300],
                )

                if resp.status in (200, 201):
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        import json as _json
                        data = _json.loads(body)

                    # Try various possible URL field names
                    url = (
                        data.get("Url")
                        or data.get("url")
                        or data.get("PaymentUrl")
                        or data.get("paymentUrl")
                        or data.get("InvoiceUrl")
                        or data.get("invoiceUrl")
                        or data.get("RedirectUrl")
                        or data.get("redirectUrl")
                    )
                    if url:
                        logger.info(
                            "Express-pay invoice created for %s: %s",
                            telegram_id,
                            str(url)[:80],
                        )
                        return str(url)

                    logger.error("Express-pay: no URL field in response: %s", data)
                else:
                    logger.error(
                        "Express-pay API error %s: %s", resp.status, body[:300]
                    )

    except asyncio.TimeoutError:
        logger.error("Express-pay API timeout for user %s", telegram_id)
    except Exception as exc:
        logger.error("Express-pay invoice creation failed: %s", exc)

    return None
