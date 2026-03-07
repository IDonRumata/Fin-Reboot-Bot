"""Daily database backup — pg_dump → gzip → send to Telegram admin.

Runs as a scheduled job at 3:00 AM daily. Keeps the last 7 backups
on disk and sends each new backup as a Telegram document.
"""

from __future__ import annotations

import asyncio
import gzip
import logging
import os
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile

from bot.core.config import settings

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("/app/backups")
MAX_BACKUPS = 7


async def create_and_send_backup(bot: Bot, send_to_chat_id: int | None = None) -> None:
    """Create a pg_dump backup and send it to admin via Telegram."""
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        sql_filename = f"finbot_backup_{timestamp}.sql"
        gz_filename = f"{sql_filename}.gz"
        gz_path = BACKUP_DIR / gz_filename

        # Parse database URL to get connection params
        # Format: postgresql+asyncpg://user:pass@host:port/dbname
        db_url = settings.database_url
        # Remove the driver prefix
        clean_url = db_url.replace("postgresql+asyncpg://", "")
        user_pass, host_db = clean_url.split("@", 1)
        db_user, db_pass = user_pass.split(":", 1)
        host_port, db_name = host_db.split("/", 1)
        db_host, db_port = host_port.split(":", 1)

        # Run pg_dump as subprocess
        env = os.environ.copy()
        env["PGPASSWORD"] = db_pass

        process = await asyncio.create_subprocess_exec(
            "pg_dump",
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            "-d", db_name,
            "--no-owner",
            "--no-privileges",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error("pg_dump failed: %s", stderr.decode())
            return

        if not stdout:
            logger.error("pg_dump returned empty output")
            return

        # Compress with gzip
        with gzip.open(gz_path, "wb") as f:
            f.write(stdout)

        file_size_kb = gz_path.stat().st_size / 1024
        logger.info("Backup created: %s (%.1f KB)", gz_filename, file_size_kb)

        # Send to all admins via Telegram
        backup_bytes = gz_path.read_bytes()
        doc = BufferedInputFile(backup_bytes, filename=gz_filename)
        caption = (
            f"📦 <b>Бэкап БД</b> — {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"📏 Размер: {file_size_kb:.1f} KB\n\n"
            f"<i>Восстановление: gunzip {gz_filename} && "
            f"psql -U finbot -d finbot_db < {sql_filename}</i>"
        )

        # Determine who to send the backup to
        target_chats = set(settings.admin_ids)
        if send_to_chat_id:
            target_chats.add(send_to_chat_id)

        for chat_id in target_chats:
            try:
                # We need to recreate the BufferedInputFile for each send
                doc = BufferedInputFile(backup_bytes, filename=gz_filename)
                await bot.send_document(
                    chat_id=chat_id,
                    document=doc,
                    caption=caption,
                )
                logger.info("Backup sent to chat %s", chat_id)
            except Exception as exc:
                logger.error("Failed to send backup to chat %s: %s", chat_id, exc)

        # Clean up old backups (keep last MAX_BACKUPS)
        _cleanup_old_backups()

    except Exception as exc:
        logger.error("Backup failed: %s", exc, exc_info=True)
        # Try to notify admin about failure
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"❌ <b>Ошибка бэкапа БД:</b>\n<code>{exc}</code>",
                )
            except Exception:
                pass


def _cleanup_old_backups() -> None:
    """Remove old backup files, keeping only the latest MAX_BACKUPS."""
    if not BACKUP_DIR.exists():
        return

    backups = sorted(BACKUP_DIR.glob("finbot_backup_*.sql.gz"), reverse=True)
    for old in backups[MAX_BACKUPS:]:
        old.unlink()
        logger.info("Removed old backup: %s", old.name)
