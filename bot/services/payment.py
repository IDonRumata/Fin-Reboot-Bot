"""bePaid payment integration - create checkout links and process webhooks."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from bot.core.config import settings

logger = logging.getLogger(__name__)


async def create_checkout_link(
    amount: int,
    description: str,
    telegram_id: int,
    webhook_url: str,
) -> str | None:
    """Create a bePaid checkout link.

    Args:
        amount: Amount in minor units (e.g. 2990 = 29.90 BYN).
        description: Payment description.
        telegram_id: Used as tracking_id for webhook matching.
        webhook_url: URL that bePaid will POST to on payment success.

    Returns:
        Checkout redirect URL or None on error.
    """
    if not settings.bepaid_shop_id or not settings.bepaid_secret_key:
        logger.warning("bePaid credentials not configured.")
        return None

    payload: dict[str, Any] = {
        "checkout": {
            "test": False,
            "transaction_type": "payment",
            "order": {
                "amount": amount,
                "currency": "BYN",
                "description": description,
                "tracking_id": str(telegram_id),
            },
            "settings": {
                "success_url": "https://t.me/fin_reboot_bot",
                "decline_url": "https://t.me/fin_reboot_bot",
                "fail_url": "https://t.me/fin_reboot_bot",
                "notification_url": webhook_url,
                "language": "ru",
                "customer_fields": {"visible": [], "read_only": []},
            },
        }
    }

    try:
        auth = aiohttp.BasicAuth(
            login=settings.bepaid_shop_id,
            password=settings.bepaid_secret_key,
        )
        async with aiohttp.ClientSession() as client:
            async with client.post(
                settings.bepaid_checkout_url,
                json=payload,
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    redirect_url: str = data.get("checkout", {}).get("redirect_url", "")
                    return redirect_url or None
                else:
                    text = await resp.text()
                    logger.error("bePaid error %s: %s", resp.status, text)
                    return None
    except Exception as exc:
        logger.error("bePaid request failed: %s", exc)
        return None
