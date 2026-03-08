"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Bot configuration. All values come from .env or environment."""

    # -- Telegram --
    bot_token: str
    admin_ids: list[int] = Field(default_factory=list)

    # -- Database --
    database_url: str = "postgresql+asyncpg://finbot:finbot_pass@postgres:5432/finbot_db"

    # -- Redis --
    redis_url: str = "redis://redis:6379/0"

    # -- bePaid --
    bepaid_shop_id: str = ""
    bepaid_secret_key: str = ""
    bepaid_checkout_url: str = "https://checkout.bepaid.by/ctp/api/checkouts"
    bepaid_payment_url: str = "https://checkout.bepaid.by/v2/confirm_order/prd_74d43b5eb24b4f0c/33685"
    bepaid_webhook_secret: str = ""  # from bePaid dashboard → Products → Webhook
    bepaid_notification_url: str = ""  # public URL for bePaid callbacks, e.g. http://185.229.251.166:8443/webhook/bepaid

    # -- Webhook server --
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8443

    # -- WebApps --
    webapp_calc_url: str = "https://t.me/fin_reboot_bot/calc"
    webapp_tracker_url: str = "https://t.me/fin_reboot_bot/tracker"

    # -- Misc --
    support_username: str = "@suportfinreboot_bot"
    participants_chat_url: str = "https://t.me/+Dwg2Qlm42xEwYWNi"
    log_level: str = "INFO"

    # -- Scheduler --
    day_scheduler_interval_minutes: int = 3
    reminder_interval_hours: int = 6

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()  # type: ignore[call-arg]
