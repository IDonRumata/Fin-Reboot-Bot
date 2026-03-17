"""
CLI-интерфейс контент-завода.
Использование:
  python main.py generate pushup_invest_1    — сгенерировать пакет для темы
  python main.py topics                       — список всех тем
  python main.py week                         — генерировать темы текущей недели
  python main.py setup-sheets                 — настроить Google Sheets
  python main.py bot                          — запустить Telegram-бота ревью
  python main.py scheduler                    — запустить планировщик
  python main.py pushup                       — показать статистику челенджа
"""
import sys
import asyncio

from config import get_pushup_stats


def cmd_generate(args: list[str]):
    from gemini_generator import ContentGenerator
    if not args:
        print("❌ Укажи topic_id. Пример: python main.py generate pushup_invest_1")
        cmd_topics([])
        return
    topic_id = args[0]
    gen = ContentGenerator()
    print(f"\n⏳ Генерирую пакет для темы '{topic_id}'...\n")
    try:
        package = gen.generate_full_content_package(topic_id)
        _print_package(package)
    except ValueError as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ Ошибка API: {e}")


def cmd_topics(_args):
    from gemini_generator import ContentGenerator
    ContentGenerator().list_topics()


def cmd_week(_args):
    from scheduler import _get_topics_for_this_week
    from gemini_generator import ContentGenerator
    topics = _get_topics_for_this_week()
    gen = ContentGenerator()
    print(f"\n📅 Темы этой недели: {topics}\n")
    for t in topics:
        print(f"\n⏳ Генерирую '{t}'...")
        package = gen.generate_full_content_package(t)
        _print_package(package)


def cmd_setup_sheets(_args):
    from sheets_manager import SheetsManager
    print("⏳ Настраиваю Google Sheets...")
    SheetsManager().setup_spreadsheet()


def cmd_bot(_args):
    from telegram_publisher import main as bot_main
    asyncio.run(bot_main())


def cmd_scheduler(_args):
    from scheduler import main as sched_main
    sched_main()


def cmd_pushup(_args):
    stats = get_pushup_stats()
    print(f"\n🏋️ ЧЕЛЕНДЖ С ОТЖИМАНИЯМИ")
    print(f"{'─' * 35}")
    print(f"📅 Старт: {stats['start_date']}")
    print(f"📆 Сегодня: день {stats['day']}")
    print(f"💪 Сегодня отжиманий: {stats['current_count']}")
    print(f"📊 Всего сделано: {stats['total_pushups_done']:,}")
    print(f"🎯 Прогноз на год: {stats['year_end_forecast']}")
    progress = stats['day'] / 365 * 100
    bar = "█" * int(progress / 5) + "░" * (20 - int(progress / 5))
    print(f"📈 Прогресс: [{bar}] {progress:.1f}%\n")


def _print_package(package: dict):
    print(f"\n{'═' * 50}")
    print(f"📦 ТЕМА: {package['topic'][:70]}")
    print(f"{'─' * 50}")
    print(f"🎬 СКРИПТ TIKTOK:\n{package['tiktok_script']}")
    print(f"\n{'─' * 50}")
    print(f"📱 ПОСТ GRAFIN:\n{package['grafin_post']}")
    print(f"\n{'─' * 50}")
    print(f"📲 INSTAGRAM:\n{package['instagram_caption']}")
    print(f"\n{'─' * 50}")
    print(f"🧪 A/B ХУКИ:\n{package['ab_hooks']}")
    print(f"{'═' * 50}\n")
    print(f"✅ Сохранено в content_output/")


COMMANDS = {
    "generate": cmd_generate,
    "topics": cmd_topics,
    "week": cmd_week,
    "setup-sheets": cmd_setup_sheets,
    "bot": cmd_bot,
    "scheduler": cmd_scheduler,
    "pushup": cmd_pushup,
}

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in COMMANDS:
        print(__doc__)
        print("Доступные команды:", ", ".join(COMMANDS.keys()))
    else:
        COMMANDS[args[0]](args[1:])
