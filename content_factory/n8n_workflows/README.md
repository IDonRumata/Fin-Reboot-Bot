# n8n Workflows для FinReboot Content Factory

## Установка n8n на VPS Beget

```bash
# Установка через npm
npm install -g n8n

# Или через Docker (рекомендуется)
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n

# Запуск через PM2 (чтобы не падал)
npm install -g pm2
pm2 start n8n --name "content-factory"
pm2 save && pm2 startup
```

После запуска: http://your-vps-ip:5678

## Список Workflows

| Файл | Описание | Триггер |
|---|---|---|
| 01_weekly_content.json | Генерация контента по расписанию | Пн/Чт 09:00 |
| 02_grafin_autopublish.json | Авто-публикация в ГраФин | По вебхуку одобрения |
| 03_daily_report.json | Ежедневный отчёт в Telegram | Ежедн. 08:00 |
| 04_bot_stats_report.json | Статистика из FinReboot бота | Ежедн. 20:00 |
| **05_grafin_video_pipeline.json** | **Полный пайплайн: генерация + ревью + видео + кросс-платформенная публикация** | **Пн/Чт 09:00 Минск + webhook** |

## Порядок настройки

1. Импортировать workflow JSON в n8n (меню → Import)
2. Настроить credentials:
   - Telegram Bot API (токен бота)
   - HTTP Request (для Gemini API)
   - Google Sheets (OAuth2 или сервисный аккаунт)
3. Активировать workflow

---

## Workflow 05: GraFin Video Pipeline — подробное описание

### Архитектура

```
[Schedule: Пн/Чт 09:00 Минск]
        |
        v
[Select Topic] — выбор темы по номеру недели
        |
        v
[HTTP POST localhost:8000/generate] — Python генератор (Gemini 2.5 Flash)
        |
        v
[Format Review] — форматирование для Telegram
        |
        v
[Send to Andrey] — сообщение с inline-кнопками
        |
  (Андрей нажимает кнопку)
        |
        v
[Webhook: /grafin-approval] — Python бот отправляет POST
        |
        v
[Router] — pub_grafin / pub_all
   |              |
   v              v
[@roboowner]   [@roboowner] + [Upload-Post → TikTok/Instagram/YouTube]
```

### Опциональная ветка: генерация видео через HeyGen

```
[Кнопка "Создать видео"] → [HeyGen API] → [Poll status каждые 30с]
        → [Видео готово] → ссылка Андрею → публикация через Upload-Post
```

### Необходимые переменные n8n (Settings → Variables)

| Переменная | Описание | Обязательна |
|---|---|---|
| ANDREY_TELEGRAM_ID | Telegram user ID | Да |
| UPLOAD_POST_API_KEY | API ключ upload-post.com | Для TikTok/Insta/YT |
| HEYGEN_API_KEY | API ключ HeyGen | Для видео с аватаром |
| HEYGEN_AVATAR_ID | ID аватара HeyGen | Для видео с аватаром |
| HEYGEN_VOICE_ID | ID голоса HeyGen | Для видео с аватаром |

### Что нужно доработать в Python боте

Python бот (@grafinwriter_bot) должен при нажатии inline-кнопок
отправлять POST на webhook n8n:

```python
import httpx

async def on_approval_callback(action, topic_id, package):
    await httpx.AsyncClient().post(
        "http://localhost:5678/webhook/grafin-approval",
        json={
            "action": action,           # "pub_grafin" или "pub_all"
            "topic_id": topic_id,
            "grafin_post": package["grafin_post"],
            "instagram_caption": package["instagram_caption"],
            "tiktok_description": package["tiktok_description"],
            "video_url": package.get("video_url", ""),
        }
    )
```
