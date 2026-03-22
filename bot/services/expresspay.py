"""Express-pay.by API client — invoice creation with HMAC-SHA1 signature.

API docs: https://express-pay.by/docs/api/v1
Endpoints:
  POST /v1/web_cardinvoices  — card payment (returns FormUrl)
  POST /v1/web_invoices      — ERIP payment (returns InvoiceUrl)

For web_ endpoints:
  - Token is included in signature computation but REMOVED from POST body.
  - Data is sent as POST form body (not query params).
  - Amount uses comma as decimal separator ("45,00").
  - ReturnType=json to get URL in response.

Auth: HMAC-SHA1 signature (uppercase hex) using secret word.
Currency: 933 = BYN.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json as _json
import logging
from datetime import datetime, timedelta, timezone

import aiohttp

from bot.core.config import settings

logger = logging.getLogger(__name__)

EXPRESSPAY_API_URL = "https://api.express-pay.by/v1/"
BYN_CURRENCY_CODE = "933"


def _compute_signature(params: dict, fields: list[str], secret_word: str) -> str:
    """HMAC-SHA1 signature: concatenate field values in order, sign with secret."""
    data = "".join(str(params.get(f, "")) for f in fields)
    return hmac.new(
        secret_word.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha1,
    ).hexdigest().upper()


# Field order per docs section "Цифровая подпись", item 16
_WEB_INVOICE_FIELDS = [
    "Token", "ServiceId", "AccountNo", "Amount", "Currency",
    "Expiration", "Info", "Surname", "FirstName", "Patronymic",
    "City", "Street", "House", "Building", "Apartment",
    "IsNameEditable", "IsAddressEditable", "IsAmountEditable",
    "EmailNotification", "SmsPhone", "ReturnType", "ReturnUrl",
    "FailUrl", "ReturnInvoiceUrl",
]

# Field order per docs section "Цифровая подпись", item 17
_WEB_CARD_INVOICE_FIELDS = [
    "Token", "ServiceId", "AccountNo", "Expiration", "Amount",
    "Currency", "Info", "ReturnUrl", "FailUrl", "Language",
    "SessionTimeoutSecs", "ExpirationDate", "ReturnType",
    "ReturnInvoiceUrl",
]


async def create_invoice(telegram_id: int) -> str | None:
    """Create Express-pay invoice and return payment URL."""
    if not settings.expresspay_api_key or not settings.expresspay_service_id:
        logger.warning("Express-pay not configured")
        return None

    secret = settings.expresspay_secret_word
    if not secret:
        logger.warning("Express-pay secret word not configured (required for web_ endpoints)")
        return None

    expiration = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime(
        "%Y%m%d"
    )

    base_params = {
        "Token": settings.expresspay_api_key,
        "ServiceId": settings.expresspay_service_id,
        "AccountNo": str(telegram_id),
        "Amount": "45,00",
        "Currency": BYN_CURRENCY_CODE,
        "Expiration": expiration,
        "Info": f"Графин (ID: {telegram_id})",
        "ReturnUrl": f"https://t.me/{settings.bot_username}?start=payment_success",
        "FailUrl": f"https://t.me/{settings.bot_username}?start=payment_fail",
        "Language": "ru",
        "ReturnType": "json",
        "ReturnInvoiceUrl": "1",
    }

    try:
        async with aiohttp.ClientSession() as http:
            # Try card payment first
            card_params = dict(base_params)
            card_params["Signature"] = _compute_signature(
                card_params, _WEB_CARD_INVOICE_FIELDS, secret,
            )
            # Token must be removed from POST body for web_ endpoints
            card_post = {k: v for k, v in card_params.items() if k != "Token"}

            url = await _call_endpoint(http, "web_cardinvoices", card_post, telegram_id)
            if url:
                return url

            # Fallback to ERIP
            erip_params = dict(base_params)
            erip_params["Signature"] = _compute_signature(
                erip_params, _WEB_INVOICE_FIELDS, secret,
            )
            erip_post = {k: v for k, v in erip_params.items() if k != "Token"}

            url = await _call_endpoint(http, "web_invoices", erip_post, telegram_id)
            if url:
                return url

    except asyncio.TimeoutError:
        logger.error("Express-pay API timeout for user %s", telegram_id)
    except Exception as exc:
        logger.error("Express-pay invoice creation failed: %s", exc)

    return None


async def _call_endpoint(
    http: aiohttp.ClientSession,
    endpoint: str,
    form_data: dict,
    telegram_id: int,
) -> str | None:
    """Call Express-pay endpoint with form POST and extract payment URL."""
    try:
        async with http.post(
            f"{EXPRESSPAY_API_URL}{endpoint}",
            data=form_data,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            body = await resp.text()
            logger.info(
                "Express-pay /%s for %s: status=%s body=%s",
                endpoint, telegram_id, resp.status, body[:500],
            )

            if resp.status in (200, 201):
                try:
                    data = _json.loads(body)
                except Exception:
                    logger.error("Express-pay: JSON parse error: %s", body[:200])
                    return None

                # Check for errors (list or dict)
                errors = data.get("Errors", [])
                if errors:
                    logger.error("Express-pay /%s errors: %s", endpoint, errors)
                    return None
                error = data.get("Error")
                if error:
                    logger.error("Express-pay /%s error: %s", endpoint, error)
                    return None

                url = (
                    data.get("FormUrl")
                    or data.get("InvoiceUrl")
                    or data.get("Url")
                )
                if url:
                    logger.info("Express-pay /%s OK for %s: %s", endpoint, telegram_id, str(url)[:80])
                    return str(url)

                logger.error("Express-pay /%s: no URL in response: %s", endpoint, data)
            else:
                logger.error("Express-pay /%s HTTP %s: %s", endpoint, resp.status, body[:300])

    except asyncio.TimeoutError:
        logger.error("Express-pay /%s timeout", endpoint)
    except Exception as exc:
        logger.error("Express-pay /%s error: %s", endpoint, exc)

    return None
