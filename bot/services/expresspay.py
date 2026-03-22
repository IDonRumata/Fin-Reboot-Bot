"""Express-pay.by API client — invoice creation and webhook handling.

API docs: https://express-pay.by/docs/api/v1
Endpoints:
  POST /v1/web_cardinvoices  — card payment (returns FormUrl + InvoiceUrl)
  POST /v1/web_invoices      — ERIP payment (returns InvoiceUrl)
Auth: Token as query parameter.
Currency: 933 = BYN.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiohttp

from bot.core.config import settings

logger = logging.getLogger(__name__)

EXPRESSPAY_API_URL = "https://api.express-pay.by/v1/"
BYN_CURRENCY_CODE = 933  # ISO 4217 numeric code for Belarusian Ruble


async def create_invoice(telegram_id: int) -> str | None:
    """Create Express-pay card invoice and return payment URL.

    Uses /web_cardinvoices endpoint (card payment).
    Returns FormUrl (payment form) on success, None on failure.
    """
    if not settings.expresspay_api_key or not settings.expresspay_service_id:
        logger.warning("Express-pay not configured (missing api_key or service_id)")
        return None

    # Invoice expires in 24 hours
    expiration = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    params = {
        "Token": settings.expresspay_api_key,
        "ServiceId": settings.expresspay_service_id,
        "AccountNo": str(telegram_id),
        "Amount": "45.00",
        "Currency": str(BYN_CURRENCY_CODE),
        "Expiration": expiration,
        "ReturnUrl": f"https://t.me/{settings.bot_username}?start=payment_success",
        "FailUrl": f"https://t.me/{settings.bot_username}?start=payment_fail",
        "Language": "ru",
        "Info": f"Графин - база знаний по инвестициям (ID: {telegram_id})",
    }

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{EXPRESSPAY_API_URL}web_cardinvoices",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                body = await resp.text()
                logger.info(
                    "Express-pay /web_cardinvoices for %s: status=%s body=%s",
                    telegram_id,
                    resp.status,
                    body[:400],
                )

                if resp.status in (200, 201):
                    import json as _json
                    try:
                        data = _json.loads(body)
                    except Exception:
                        logger.error("Express-pay: failed to parse JSON: %s", body[:200])
                        return None

                    # Card invoice returns FormUrl (payment form) and InvoiceUrl (ERIP)
                    url = (
                        data.get("FormUrl")
                        or data.get("InvoiceUrl")
                        or data.get("Url")
                        or data.get("url")
                    )
                    if url:
                        logger.info(
                            "Express-pay invoice created for %s: %s",
                            telegram_id,
                            str(url)[:80],
                        )
                        return str(url)

                    logger.error("Express-pay: no URL in response: %s", data)
                else:
                    logger.error(
                        "Express-pay API error %s: %s", resp.status, body[:400]
                    )

    except asyncio.TimeoutError:
        logger.error("Express-pay API timeout for user %s", telegram_id)
    except Exception as exc:
        logger.error("Express-pay invoice creation failed: %s", exc)

    return None
