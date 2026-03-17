# Настройка контент-завода: пошаговый гайд

## Шаг 1: Установка Python зависимостей

```bash
cd "D:\Claude Code doc\fin_reboot_bot\content_factory"
pip install -r requirements.txt
```

## Шаг 2: Создать .env файл

```bash
copy .env.example .env
# Открой .env и заполни:
```

### 2.1 Получить Gemini API ключ
1. Зайди на https://aistudio.google.com/app/apikey
2. Войди через свой Google аккаунт (у тебя есть подписка Pro)
3. Нажми "Create API Key"
4. Скопируй в GEMINI_API_KEY=...

### 2.2 Создать нового Telegram-бота для контент-завода
1. Открой @BotFather в Telegram
2. /newbot → дай имя (например "FinRebootContent")
3. Скопируй токен в TELEGRAM_BOT_TOKEN=...
4. Свой Telegram ID: зайди @userinfobot → скопируй id в ANDREY_TELEGRAM_ID=...

### 2.3 ID канала ГраФин
1. Перешли любое сообщение из канала боту @userinfobot
2. Он покажет ID канала (начинается с -100...)
3. Вставь в GRAFIN_CHANNEL_ID=...
4. Добавь нового бота в канал как администратора (права: отправка сообщений)

## Шаг 3: Google Sheets (опционально, но рекомендуется)

### 3.1 Создать сервисный аккаунт
1. Зайди на https://console.cloud.google.com
2. Создай новый проект (например "finreboot-content")
3. APIs & Services → Enable APIs → включи:
   - Google Sheets API
   - Google Drive API
4. Credentials → Create Credentials → Service Account
5. Скачай JSON файл → сохрани как `credentials.json` в папку content_factory/
6. Скопируй email сервисного аккаунта (вида xxx@yyy.iam.gserviceaccount.com)

### 3.2 Создать таблицу
1. Создай новую Google Таблицу
2. Скопируй ID из URL (между /d/ и /edit)
3. Вставь в CONTENT_SHEET_ID=...
4. Поделись таблицей с email сервисного аккаунта (роль: Редактор)

### 3.3 Инициализировать таблицу
```bash
python main.py setup-sheets
```

## Шаг 4: Первый тест

```bash
# Посмотреть статистику челенджа
python main.py pushup

# Список тем
python main.py topics

# Сгенерировать первый пакет контента
python main.py generate pushup_invest_1
```

## Шаг 5: Запустить Telegram-бота для ревью

```bash
python main.py bot
```

После запуска:
- Напиши боту /topics — увидишь список тем
- Напиши /generate pushup_invest_1 — получишь пакет на ревью
- Нажми ✅ — опубликуется в ГраФин

## Шаг 6: Настроить автоматический планировщик

На VPS Beget (уже есть):
```bash
# Зайти на VPS по SSH
ssh user@your-vps-ip

# Перенести файлы
scp -r "D:\Claude Code doc\fin_reboot_bot\content_factory" user@vps-ip:~/content_factory/

# Установить зависимости
cd ~/content_factory && pip install -r requirements.txt

# Создать .env (заполнить на сервере)
cp .env.example .env && nano .env

# Запустить через PM2
npm install -g pm2
pm2 start "python scheduler.py" --name "content-factory"
pm2 save && pm2 startup
```

## Шаг 7: Импорт n8n Workflows (на VPS)

1. Открой n8n: http://your-vps-ip:5678
2. Меню → Import from File
3. Загрузи `n8n_workflows/01_weekly_content.json`
4. В Settings → Variables добавь ANDREY_TELEGRAM_ID
5. В Credentials добавь Telegram Bot API
6. Активируй workflow

---

## Структура файлов

```
content_factory/
├── main.py                 ← CLI интерфейс (запускай отсюда)
├── gemini_generator.py     ← Генерация через Gemini API
├── telegram_publisher.py   ← Бот для ревью и публикации
├── sheets_manager.py       ← Google Sheets интеграция
├── scheduler.py            ← Планировщик (PM2 на VPS)
├── config.py               ← Настройки
├── .env                    ← Твои API ключи (НЕ коммитить в git!)
├── prompts/                ← Шаблоны промптов
├── n8n_workflows/          ← Готовые workflows для n8n
├── scripts_ready/          ← Готовые скрипты для съёмки
└── content_output/         ← Сгенерированный контент (JSON)
```

## .gitignore (добавить в основной .gitignore бота)

```
content_factory/.env
content_factory/credentials.json
content_factory/content_output/
```
