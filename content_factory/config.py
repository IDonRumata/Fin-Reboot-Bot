import os
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANDREY_TELEGRAM_ID = int(os.getenv("ANDREY_TELEGRAM_ID", "0"))
GRAFIN_CHANNEL_ID = int(os.getenv("GRAFIN_CHANNEL_ID", "0"))
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
CONTENT_SHEET_ID = os.getenv("CONTENT_SHEET_ID")
AUTHOR_NAME = os.getenv("AUTHOR_NAME", "Андрей")

PUSHUP_CHALLENGE_START = date(2025, 10, 25)
PUSHUP_START_COUNT = 10


def get_pushup_stats() -> dict:
    """Рассчитывает текущие показатели челенджа с отжиманиями."""
    today = date.today()
    day_number = (today - PUSHUP_CHALLENGE_START).days + 1
    current_count = PUSHUP_START_COUNT + (day_number - 1)
    year_end_count = PUSHUP_START_COUNT + 364  # день 365
    total_done = sum(PUSHUP_START_COUNT + i for i in range(day_number))
    return {
        "day": day_number,
        "current_count": current_count,
        "year_end_forecast": year_end_count,
        "total_pushups_done": total_done,
        "start_date": PUSHUP_CHALLENGE_START.strftime("%d.%m.%Y"),
    }
