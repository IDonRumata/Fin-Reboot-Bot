# Технический бриф: Telegram-бот «Графин»

## Репозиторий и инфраструктура

- **GitHub:** `https://github.com/IDonRumata/Fin-Reboot-Bot`
- **Локальный путь:** `D:\Claude Code doc\fin_reboot_bot`
- **VPS Beget:** IP `85.117.235.247`, путь `/root/Fin-Reboot-Bot`
- **VPS Zomro:** второй сервер (есть, пока не используется для бота)
- **Docker-контейнер:** `fin-reboot-bot-bot-1` (строго через дефисы)

### Деплой на сервер

```bash
cd /root/Fin-Reboot-Bot && git pull && \
docker build -t fin-reboot-bot-bot . && \
docker stop fin-reboot-bot-bot-1 && \
docker rm fin-reboot-bot-bot-1 && \
docker run -d --name fin-reboot-bot-bot-1 \
  --env-file .env --restart unless-stopped \
  -p 8443:8443 \
  -v ./data:/app/data \
  -v ./Slides:/app/slides:ro \
  -v fin-reboot-bot_backups:/app/backups \
  --network fin-reboot-bot_default fin-reboot-bot-bot
```

---

## Стек

| Компонент | Технология |
|---|---|
| Язык | Python (async) |
| Telegram-фреймворк | aiogram 3.x |
| База данных | PostgreSQL + SQLAlchemy (asyncpg) |
| Миграции | Alembic |
| Кэш / FSM-хранилище | Redis |
| Платежи | bePaid (основной), ExpressPay (интегрирован, не активен) |
| Планировщик | APScheduler (AsyncIOScheduler) |
| Webhook-сервер | aiohttp (порт 8443) |
| Конфигурация | pydantic-settings (.env) |

---

## Структура проекта

```
fin_reboot_bot/
├── bot/
│   ├── core/
│   │   ├── config.py          # Все настройки из .env
│   │   └── bot_instance.py    # Создание Bot и Dispatcher
│   ├── database/
│   │   ├── models.py          # SQLAlchemy-модели
│   │   ├── repositories.py    # Все SQL-запросы
│   │   └── engine.py          # Подключение к БД
│   ├── handlers/
│   │   ├── start.py           # /start + deep link + UTM
│   │   ├── quiz.py            # Квиз FSM (6 вопросов)
│   │   ├── buy.py             # Покупка / оплата
│   │   ├── menu.py            # /menu, about, support
│   │   ├── progress.py        # /progress
│   │   ├── day_done.py        # day_X_done callback
│   │   ├── continue_block.py  # cont_dX_bY callback
│   │   ├── keywords.py        # АРЕНДА, РОБОТ
│   │   ├── admin.py           # Все /admin-команды
│   │   └── fallback.py        # Catch-all (последний)
│   ├── middlewares/
│   │   ├── db_session.py      # Инжекция сессии БД
│   │   ├── antiflood.py       # Rate limit 0.5 сек
│   │   └── logging_mw.py      # Логирование всех событий
│   ├── services/
│   │   ├── content_sender.py  # Отправка блоков контента
│   │   ├── payment.py         # bePaid API (создание ссылки)
│   │   ├── expresspay.py      # ExpressPay (интегрирован)
│   │   ├── user_service.py    # Бизнес-логика пользователя
│   │   └── webhook.py         # aiohttp webhook app
│   ├── workers/
│   │   ├── day_scheduler.py   # Проверка и отправка следующего дня
│   │   ├── reminders.py       # Напоминания каждые 6 часов
│   │   ├── quiz_followup.py   # Фоллоу-ап тем, кто не купил
│   │   └── backup.py          # Бэкап БД в 03:00 и 15:00
│   └── main.py                # Точка входа
├── data/
│   └── content_blocks.csv     # Контент курса (5 дней)
├── Slides/                    # Картинки к курсу (1_0.png … 5_3.png)
├── alembic/                   # Миграции БД
├── content_factory/           # Генерация контента (Gemini AI)
└── .env                       # Секреты (не в git)
```

---

## База данных — модели

### `users`

| Поле | Описание |
|---|---|
| `telegram_id` | BigInt, уникальный |
| `status` | active / blocked |
| `payment_status` | none / pending / paid / failed |
| `utm_source` | deep link метка (напр. `quiz_instagram`) |
| `quiz_answers` | JSON с ответами |
| `quiz_score` | Итоговый балл (6–24) |
| `quiz_user_type` | A / B / C (тип пользователя) |
| `quiz_followup_step` | Шаг фоллоу-апа (0, 1, 2...) |
| `ab_group` | A/B тест сплит (чётный/нечётный telegram_id) |

### `user_progress`

5 дней × поля: `day_N_status` (not_started / sent / completed), `day_N_current_block`, `day_N_sent_at`, `day_N_reminder_sent`

### `content_blocks`

Контент курса: `day`, `block`, `order`, `type` (text / photo / video / video_note / voice), `content`, `file_id`, `button_text`, `button_callback`, `delay_seconds`

### `payments`

`transaction_id`, `amount` (в копейках), `payment_method`, `status`

### `leads`

`lead_type`: `arenda` или `robot` — лиды по ключевым словам

---

## Пользовательский путь (воронка)

```
Реклама Instagram
    ↓
t.me/fin_reboot_bot?start=quiz_instagram
    ↓
КВИЗ (6 вопросов) — FSM
  q1: Где хранишь деньги?
  q2: Реакция на инфляцию?
  q3: Отношение к акциям?
  q4: Финансовая цель?
  q5: Как часто думаешь о деньгах?
  q6: Цель через 10 лет?
    ↓
Ввод имени → Подсчёт очков (6–24)
    ↓
Результат: A (≤12) / B (≤18) / C (>18)
  + Лид-магнит: шпаргалка по налогам (BY / RU / KZ / UA / PL)
  + Блок авторов (Марина + Андрей)
  + Оффер: 45 BYN
    ↓
[Купить] → bePaid → Webhook → payment_status=paid
    ↓
День 1 автоматически (через day_scheduler)
    ↓
Дни 2–5 (через 24 часа после завершения предыдущего)
```

---

## Фоновые задачи (APScheduler)

| Job | Интервал | Что делает |
|---|---|---|
| `day_scheduler` | каждые 3 мин | Находит пользователей, у которых пора следующий день, отправляет контент |
| `reminders` | каждые 6 часов | Напоминает тем, кто завис на каком-то дне |
| `quiz_followup` | каждые 15 мин | Дожимает тех, кто прошёл квиз, но не купил |
| `daily_backup` | 03:00 и 15:00 | Бэкап PostgreSQL, отправляет админу |

---

## Ключевые слова (keywords.py)

- **АРЕНДА** → записывает лид `arenda`, отправляет информацию о будущем курсе по аренде
- **РОБОТ** → записывает лид `robot`, отправляет ссылку на @TestDriveFXrobot (Форекс-робот $950)

---

## Платежи

### bePaid (основной)

- Создаёт checkout-ссылку через API
- Webhook на `http://85.117.235.247:8443/webhook/bepaid`
- После успешной оплаты: `payment_status=paid` → запускается день 1

### ExpressPay

- Код написан (`bot/services/expresspay.py`), но не подключён к основному флоу

### Цена: **45 BYN** (amount в коде = 4500 копеек)

---

## Переменные окружения (.env)

```env
BOT_TOKEN=
ADMIN_IDS=123456789,987654321
DATABASE_URL=postgresql+asyncpg://finbot:finbot_pass@postgres:5432/finbot_db
REDIS_URL=redis://redis:6379/0

BEPAID_SHOP_ID=
BEPAID_SECRET_KEY=
BEPAID_WEBHOOK_SECRET=
BEPAID_NOTIFICATION_URL=http://85.117.235.247:8443/webhook/bepaid

EXPRESSPAY_API_KEY=
EXPRESSPAY_SERVICE_ID=34197
EXPRESSPAY_SECRET_WORD=
EXPRESSPAY_WEBHOOK_TOKEN=

WEBAPP_CALC_URL=https://t.me/fin_reboot_bot/calc
WEBAPP_TRACKER_URL=https://t.me/fin_reboot_bot/tracker
PARTICIPANTS_CHAT_URL=https://t.me/+Dwg2Qlm42xEwYWNi
SUPPORT_USERNAME=@suportfinreboot_bot
```

---

## Админ-команды

| Команда | Что делает |
|---|---|
| `/admin` | Список всех команд |
| `/stats` | Статистика: юзеры, оплаты, прогресс по дням, лиды |
| `/sync` | Загрузить контент из `data/content_blocks.csv` |
| `/test_send <id> <day>` | Принудительно отправить день пользователю |
| `/confirm_payment <id>` | Подтвердить оплату вручную |
| `/grant <id>` | Бесплатный доступ |
| `/reset_user <id>` | Полный сброс (квиз + оплата + прогресс) |
| `/export` | Выгрузить CSV с данными квиза |
| `/broadcast <текст>` | Рассылка всем прошедшим квиз |
| `/backup` | Принудительный бэкап БД |

---

## A/B тест

Реализован в квизе: чётный `telegram_id` → группа **A** (benefits-focused приветствие), нечётный → **B** (loss-aversion приветствие). Группа сохраняется в `users.ab_group`.

---

## Content Factory (отдельный модуль)

`fin_reboot_bot/content_factory/` — независимый модуль для генерации контента:

- **Gemini AI** (Veo) — генерация постов и скриптов
- Шаблоны промптов: `telegram_posts.py`, `instagram_captions.py`, `tiktok_scripts.py`, `grafin_posts.py`
- Google Sheets интеграция (`sheets_manager.py`)
- Автопостинг в Telegram-канал (`telegram_publisher.py`)
- API-сервер (`api_server.py`)

---

## Маркетинг (текущее состояние)

- **Рекламный аккаунт Meta:** ID `1895389781012156`, бизнес `krononchill`
- **Кампания:** Active, старт 30 марта 2026, $4/день, BY + UA + KZ, возраст 30–50
- **Ссылка входа:** `https://t.me/fin_reboot_bot?start=quiz_instagram`
- **Taplink (шапка профиля):** `https://taplink.cc/rumata`
- **Видео:** `promo_final.mp4` (720×1280, 61 сек)
- **Оплата рекламы:** Visa 1729, постоплата (Backup)
- **Техподдержка бота:** @suportfinreboot_bot

---

## Статус разработки

### Готово

- Полная воронка: реклама → квиз → оффер → оплата → курс
- 5-дневный курс с контентом (CSV + Slides)
- Платежи через bePaid
- Фоновые задачи: дни, напоминания, квиз-фоллоу-апы, бэкап
- A/B тест квиза
- UTM-трекинг
- Лид-магнит (шпаргалки по налогам BY/RU/KZ/UA/PL)
- Ключевые слова АРЕНДА / РОБОТ
- Полный набор админ-команд
- Meta Ads кампания запущена

### Не реализовано / в планах

- ExpressPay не подключён к основному флоу
- WebApp калькулятор и трекер — URL прописаны, Mini App не создан
- Второй VPS (Zomro) — не задействован
- Два домена: один под риэлторов, второй свободен (бывший n8n, можно переиспользовать)
