"""User-facing helper functions (progress bar, status text)."""

from __future__ import annotations

from bot.database.models import DayStatus, UserProgress


DAY_TITLES: dict[int, str] = {
    1: "Снимаем розовые очки",
    2: "Стратегия защиты денег",
    3: "Открываем криптокошелёк",
    4: "Открываем брокерский счёт",
    5: "Собираем портфель",
}


def build_progress_text(progress: UserProgress) -> str:
    """Build a beautiful progress-bar message."""
    lines: list[str] = [
        "━━━━━━━━━━━━━━━━━━━",
        "📊 <b>Ваш прогресс</b>",
        "━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for day in range(1, 6):
        status: DayStatus = getattr(progress, f"day_{day}_status")
        title = DAY_TITLES.get(day, "")

        if status == DayStatus.completed:
            icon = "✅"
        elif status == DayStatus.sent:
            icon = "🔄"
        else:
            icon = "⬜"

        lines.append(f"{icon} <b>День {day}:</b> {title}")

    completed = sum(
        1
        for d in range(1, 6)
        if getattr(progress, f"day_{d}_status") == DayStatus.completed
    )
    bar = "▓" * completed + "░" * (5 - completed)
    lines.append(f"\n{bar}  {completed}/5 дней")

    return "\n".join(lines)
