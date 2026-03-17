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

## Порядок настройки

1. Импортировать workflow JSON в n8n (меню → Import)
2. Настроить credentials:
   - Telegram Bot API (токен бота)
   - HTTP Request (для Gemini API)
   - Google Sheets (OAuth2 или сервисный аккаунт)
3. Активировать workflow
