"""Express-pay.by API client — invoice creation and webhook handling.

Creates payment invoices via Express-pay API.
When client pays, Express-pay sends webhook → bot activates user access.
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

    payload = {
        "serviceId": int(settings.expresspay_service_id),
        "accountNo": str(telegram_id),
        "amount": 45.00,
        "currency": "BYN",
        "expiration": expiration,
        "returnUrl": f"https://t.me/{settings.bot_username}?start=payment_success",
        "failUrl": f"https://t.me/{settings.bot_username}?start=payment_fail",
        "language": "ru",
        "info": f"Графин - база знаний по инвестициям (ID: {telegram_id})",
    }

    headers = {
        "Authorization": f"Bearer {settings.expresspay_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{EXPRESSPAY_API_URL}invoices",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                logger.info(
                    "Express-pay invoice response for %s: status=%s",
                    telegram_id,
                    resp.status,
                )

                if resp.status in (200, 201):
                    # Express-pay returns invoiceUrl or similar field
                    url = (
                        data.get("invoiceUrl")
                        or data.get("paymentUrl")
                        or data.get("url")
                    )
                    if url:
                        logger.info(
                            "Express-pay invoice created for %s: %s",
                            telegram_id,
                            url[:60],
                        )
                        return url
                    else:
                        logger.error(
                            "Express-pay: no URL in response: %s", data
                        )
                else:
                    logger.error(
                        "Express-pay API error %s: %s", resp.status, data
                    )

    except asyncio.TimeoutError:
        logger.error("Express-pay API timeout for user %s", telegram_id)
    except Exception as exc:
        logger.error("Express-pay invoice creation failed: %s", exc)

    return None
