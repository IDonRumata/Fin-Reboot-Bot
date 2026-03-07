import csv
import os

CSV_PATH = r"D:\Claude Code doc\fin_reboot_bot\data\content_blocks.csv"
OUT_PATH = r"D:\Claude Code doc\fin_reboot_bot\data\content_blocks_updated.csv"

# Terms to explain (simple replacements for text lines)
TERMS = {
    "диверсификация": "диверсификация (распределение денег между разными инструментами, чтобы не потерять всё сразу)",
    "ETF": "ETF (фонд, торгуемый на бирже — «корзина» из акций сотен компаний в одной покупке)",
    "S&P 500": "S&P 500 (индекс 500 крупнейших компаний США: Apple, Google, Amazon и др.)",
    "DCA": "DCA (Dollar Cost Averaging — стратегия регулярных покупок на одинаковую сумму)",
    "волатильность": "волатильность (сильные колебания цены вверх-вниз)",
    "Депозитарий": "Депозитарий (организация, которая хранит записи о владении вашими акциями)",
    "Индексный фонд": "Индексный фонд (фонд, который копирует состав биржевого индекса)",
    "индексный фонд": "индексный фонд (фонд, который копирует состав биржевого индекса)",
    "Сложный процент": "Сложный процент (проценты начисляются не только на вложенные деньги, но и на ранее полученные проценты)",
    "сложный процент": "сложный процент (проценты начисляются не только на вложенные деньги, но и на ранее полученные проценты)",
    "Ставка рефинансирования": "Ставка рефинансирования (процент, по которому центральный банк кредитует коммерческие банки)",
    "ставка рефинансирования": "ставка рефинансирования (процент, по которому центральный банк кредитует коммерческие банки)",
    "Портфель": "Портфель (набор ваших инвестиций в разные инструменты)",
    "портфель": "портфель (набор ваших инвестиций в разные инструменты)",
    "Свеча ": "Свеча (элемент графика, показывающий изменение цены за период) ",
    "свеча ": "свеча (элемент графика, показывающий изменение цены за период) ",
}

# The videos to insert at day X, block 1, order 0
VIDEOS = {
    1: "Video/1kurs.mp4",
    3: "Video/2kurs.mp4",
    5: "Video/3kurs.mp4",
}

rows = []
with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        rows.append(row)

new_rows = []

# Keep track of what we have inserted so we don't insert twice
inserted_videos = set()

for row in rows:
    day = int(row["day"])
    block = int(row["block"])
    order = int(row["order"])
    
    # Are we at the start of day 1, 3, or 5?
    if day in VIDEOS and block == 1 and day not in inserted_videos:
        # Insert video note first
        video_row = {
            "day": str(day),
            "block": "1",
            "order": "0",
            "type": "video_note",
            "content": "",
            "file_id": VIDEOS[day],
            "caption": "",
            "button_text": "",
            "button_callback": "",
            "parse_mode": "HTML",
            "delay_seconds": "2"
        }
        new_rows.append(video_row)
        inserted_videos.add(day)
    
    # Update order if we inserted a video at the beginning of this block
    if day in VIDEOS and block == 1:
        row["order"] = str(order + 1)
        
    # Replace terms in text content
    if row["type"] in ["text", "text_with_button", "text_with_webapp"] and row["content"]:
        content = row["content"]
        # Very naive replace, but sufficient for our needs.
        # Ensure we don't replace if it's already there (naive check)
        for term, explanation in TERMS.items():
            if term in content and explanation not in content:
                # Replace with caution, only exact matching the term
                content = content.replace(term, explanation)
        row["content"] = content
        
    new_rows.append(row)

with open(OUT_PATH, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for r in new_rows:
        writer.writerow(r)

print(f"Updated CSV written to {OUT_PATH}! Added {len(inserted_videos)} videos.")
