"""
Менеджер Google Sheets для контент-плана и аналитики.
Читает темы из таблицы, записывает статусы публикаций.
"""
import json
from datetime import datetime, date
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_CREDENTIALS_PATH, CONTENT_SHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Названия листов в таблице
SHEET_CONTENT_PLAN = "Контент-план"
SHEET_ANALYTICS = "Аналитика"
SHEET_SCRIPTS = "Скрипты"


def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
    return gspread.authorize(creds)


class SheetsManager:
    def __init__(self):
        self.client = _get_client()
        self.spreadsheet = self.client.open_by_key(CONTENT_SHEET_ID)

    def get_pending_topics(self) -> list[dict]:
        """Возвращает темы со статусом 'Новая' из контент-плана."""
        try:
            ws = self.spreadsheet.worksheet(SHEET_CONTENT_PLAN)
            records = ws.get_all_records()
            return [r for r in records if r.get("Статус", "").strip() == "Новая"]
        except gspread.exceptions.WorksheetNotFound:
            return []

    def mark_as_generated(self, row_index: int, topic_id: str):
        """Отмечает тему как 'Сгенерировано'."""
        ws = self.spreadsheet.worksheet(SHEET_CONTENT_PLAN)
        # +2: +1 за заголовок, +1 за индексацию с 1
        ws.update_cell(row_index + 2, self._col_index("Статус"), "Сгенерировано")
        ws.update_cell(row_index + 2, self._col_index("Дата генерации"), datetime.now().strftime("%d.%m.%Y %H:%M"))

    def mark_as_published(self, topic_id: str, platform: str):
        """Отмечает тему как опубликованную на платформе."""
        ws = self.spreadsheet.worksheet(SHEET_CONTENT_PLAN)
        records = ws.get_all_records()
        for i, record in enumerate(records):
            if record.get("Topic ID") == topic_id:
                ws.update_cell(i + 2, self._col_index("Статус"), f"Опубликовано: {platform}")
                ws.update_cell(i + 2, self._col_index("Дата публикации"), datetime.now().strftime("%d.%m.%Y %H:%M"))
                break

    def save_script(self, package: dict):
        """Сохраняет скрипт в лист 'Скрипты'."""
        try:
            ws = self.spreadsheet.worksheet(SHEET_SCRIPTS)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(SHEET_SCRIPTS, rows=1000, cols=10)
            ws.append_row(["Topic ID", "Тема", "Серия", "Скрипт TikTok", "Пост ГраФин", "Instagram", "A/B Хуки", "Дата"])

        ws.append_row([
            package.get("topic_id", ""),
            package.get("topic", ""),
            package.get("series", ""),
            package.get("tiktok_script", ""),
            package.get("grafin_post", ""),
            package.get("instagram_caption", ""),
            package.get("ab_hooks", ""),
            datetime.now().strftime("%d.%m.%Y %H:%M"),
        ])

    def log_analytics(self, platform: str, metric: str, value: float | int, date_val: date | None = None):
        """Записывает метрику в лист аналитики."""
        try:
            ws = self.spreadsheet.worksheet(SHEET_ANALYTICS)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(SHEET_ANALYTICS, rows=5000, cols=8)
            ws.append_row(["Дата", "Платформа", "Метрика", "Значение"])

        ws.append_row([
            (date_val or date.today()).strftime("%d.%m.%Y"),
            platform,
            metric,
            value,
        ])

    def get_content_plan_template(self) -> list[list]:
        """Возвращает шаблон заголовков для создания новой таблицы."""
        return [[
            "Topic ID", "Тема", "Серия", "Формат", "Запланировано на",
            "Статус", "Дата генерации", "Дата публикации", "Платформы", "Заметки"
        ]]

    def setup_spreadsheet(self):
        """Создаёт структуру таблицы при первом запуске."""
        try:
            ws = self.spreadsheet.worksheet(SHEET_CONTENT_PLAN)
            print(f"✅ Лист '{SHEET_CONTENT_PLAN}' уже существует")
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(SHEET_CONTENT_PLAN, rows=500, cols=10)
            ws.append_row(self.get_content_plan_template()[0])
            # Заполняем темами из CONTENT_TOPICS
            from prompts.tiktok_scripts import CONTENT_TOPICS
            for t in CONTENT_TOPICS:
                ws.append_row([
                    t["id"], t["topic"], t.get("series", ""), t.get("format", ""),
                    "", "Новая", "", "", "TikTok, Telegram, Instagram", ""
                ])
            print(f"✅ Создан лист '{SHEET_CONTENT_PLAN}' с {len(CONTENT_TOPICS)} темами")

        for sheet_name in [SHEET_ANALYTICS, SHEET_SCRIPTS]:
            try:
                self.spreadsheet.worksheet(sheet_name)
                print(f"✅ Лист '{sheet_name}' уже существует")
            except gspread.exceptions.WorksheetNotFound:
                self.spreadsheet.add_worksheet(sheet_name, rows=1000, cols=10)
                print(f"✅ Создан лист '{sheet_name}'")

    def _col_index(self, col_name: str) -> int:
        """Возвращает индекс столбца по имени (1-based)."""
        ws = self.spreadsheet.worksheet(SHEET_CONTENT_PLAN)
        headers = ws.row_values(1)
        return headers.index(col_name) + 1 if col_name in headers else 1


if __name__ == "__main__":
    mgr = SheetsManager()
    mgr.setup_spreadsheet()
    print("✅ Google Sheets настроен")
