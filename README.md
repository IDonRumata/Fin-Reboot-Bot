# Fin-Reboot: EdTech Platform with Zero-Touch Automation

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Telegram Mini App](https://img.shields.io/badge/TMA-Mini%20App-blue?logo=telegram&logoColor=white)](https://core.telegram.org/bots/webapps)
[![n8n Automation](https://img.shields.io/badge/n8n-Workflows-orange?logo=n8n&logoColor=white)](https://n8n.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Полнофункциональная платформа для продажи и доставки онлайн-курсов с полной автоматизацией. От первого клика до выдачи сертификата — всё происходит без участия автора. Интегрирует платежи (bePaid, ЕРИП, Telegram Stars), Telegram Mini Apps для интерактивности, и AI-ассистента для поддержки студентов.

---

## ✨ Ключевые возможности

| Функция | Описание |
|---------|---------|
| 💳 **Multi-Payment Gateway** | Карты (bePaid), ЕРИП (Беларусь), Telegram Stars, Apple Pay |
| 📱 **Telegram Mini Apps** | Встроенные микро-приложения: калькулятор инвестиций, финансовый чекап |
| 📚 **Smart Content Delivery** | Выдача уроков по расписанию с привязкой к времени покупки |
| 🧪 **AI-Driven Quizzes** | Claude проверяет домашние задания и даёт обратную связь |
| 🤖 **24/7 AI Mentor** | Claude отвечает на вопросы студентов по материалам курса |
| 📊 **Admin Dashboard** | Аналитика, управление контентом, массовые рассылки |
| 🎯 **Sales Funnel** | Встроенная воронка: "Бесплатный урок → Оффер → Оплата → Обучение → Upsell" |

---

## 🎯 Бизнес-ценность

Для экспертов и онлайн-школ эта платформа превращает хаотичные продажи в предсказуемый конвейер:

| Метрика | Ручное управление | С Fin-Reboot |
|---|---|---|
| **Участие автора** | Постоянный менеджмент | **0 часов** после настройки |
| **Прием платежей** | Ручные подтверждения | **Автоматический** эквайринг |
| **Доставка контента** | Группы TG / GetCourse | **Индивидуальный** темп + расписание |
| **Поддержка студентов** | Живой куратор | **24/7 AI-ассистент** |
| **Проверка ДЗ** | Ручной разбор | **Claude** с обратной связью |

---

## 🏗️ Архитектура

```
┌───────────────────────────────────────────────────┐
│ Student Landing Page (Telegram)                   │
│ • Бесплатный урок (preview)                       │
│ • Оффер (TMA с калькулятором ROI)                 │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────┐
│ Payment Processing (bePaid/ЕРИП/Stars)             │
│ • Валидация платежа → Webhook                      │
│ • Выдача доступа в БД                             │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────┐
│ Content Delivery Engine (n8n automation)          │
│ • Выдача модуля по расписанию                     │
│ • Email/TG напоминания                            │
│ • Запуск задания (quiz/HW)                        │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────┐
│ Learning Experience Layer                         │
│ • TMA для интерактивных модулей                   │
│ • AI Mentor (Claude) — Q&A в реальном времени     │
│ • Quiz Grading (Claude) — проверка ДЗ             │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────┐
│ Completion & Upsell                               │
│ • Сертификат                                      │
│ • Cross-sell (новый курс, консультация)           │
└───────────────────────────────────────────────────┘
```

---

## 🛠️ Стек технологий

**Backend:**
- Python 3.11+ (aiogram 3.x)
- PostgreSQL 16 + Alembic (миграции)
- SQLAlchemy (async ORM)

**Automation & Workflows:**
- n8n (оркестрация платежей, рассылки, расписание контента)
- Telegram Bot API
- Telegram Mini Apps SDK (React)

**Payments:**
- bePaid API (карты, e-wallets в СНГ)
- ЕРИП (система расчетов Беларуси)
- Telegram Stars API

**AI & Content:**
- Anthropic Claude (ассистент, проверка ДЗ)

**Deployment:**
- Docker + Docker Compose
- Systemd service или cloud platform

---

## 🚀 Быстрый старт

### 1️⃣ Установка

```bash
git clone https://github.com/IDonRumata/Fin-Reboot-Bot.git
cd Fin-Reboot-Bot

python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows

pip install -r requirements.txt
```

### 2️⃣ Конфигурация

```bash
cp .env.example .env
nano .env  # Заполни значения (см. таблица ниже)

# Инициализация БД
python -c "from database import init_db; init_db()"
# или если используешь Alembic:
alembic upgrade head
```

### 3️⃣ n8n Workflows

Импортируй workflows из папки `workflows/`:
1. Откой n8n (локально или cloud)
2. Import JSON файлы для платежей, расписания, уведомлений

### 4️⃣ Запуск

```bash
# Локальная разработка
python main.py

# Docker
docker compose up -d
docker compose logs -f bot
```

---

## ⚙️ Конфигурация

### Обязательные переменные

| Переменная | Пример | Где получить |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `123456:ABCdef...` | [@BotFather](https://t.me/botfather) |
| `ADMIN_TELEGRAM_ID` | `987654321` | [@userinfobot](https://t.me/userinfobot) |
| `DATABASE_URL` | `postgresql://user:pass@localhost/fin_reboot` | Твой PostgreSQL |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | [console.anthropic.com](https://console.anthropic.com) |
| `BEPAID_SHOP_ID` | `12345` | [bepaid.by](https://bepaid.by/) → API Keys |
| `BEPAID_API_TOKEN` | `secret_token` | bePaid dashboard |

### Optional: Telegram Mini Apps

| Переменная | Назначение |
|---|---|
| `MINI_APP_URL` | URL где развёрнут React Mini App (например, Vercel) |

### Параметры обучения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `LESSON_RELEASE_TIME` | `09:00` | В какое время выпускать новый урок |
| `QUIZ_TIMEOUT_HOURS` | 24 | Сколько часов студент может решать задание |
| `UPSELL_DELAY_DAYS` | 3 | Через сколько дней после завершения предлагать новый курс |
| `AI_MENTOR_ENABLED` | `true` | Включить AI-ассистента |

---

## 🤖 Команды бота

| Команда | Действие |
|---|---|
| `/start` | Начало работы, предложение бесплатного урока |
| `/buy` | Показать оффер (TMA с калькулятором) |
| `/my_course` | Мой курс — доступные уроки |
| `/homework` | Список заданий на проверку |
| `/ask_mentor` | Спросить у AI-ассистента |
| `/progress` | Прогресс по курсу |
| `/admin` | Admin dashboard (только для админа) |
| `/help` | Справка |

---

## 💳 Интеграция платежей

### bePaid (для СНГ)

1. Регистрируешься на [bepaid.by](https://bepaid.by/)
2. Создаёшь Shop с API token
3. В `.env` указываешь `BEPAID_SHOP_ID` и `BEPAID_API_TOKEN`
4. n8n webhook автоматически обрабатывает уведомления о платеже

### ЕРИП (Беларусь)

1. Подключаешься через bePaid (они поддерживают ЕРИП)
2. При создании платежа выбираешь способ "ЕРИП"

### Telegram Stars

1. Указываешь `STARS_PAYMENT_ENABLED=true` в `.env`
2. Бот автоматически обрабатывает платежи Stars

---

## 📊 Примеры использования

### Запустить новый курс

1. **Подготовить контент:**
   ```
   Модуль 1 (бесплатный) → 3 платных модуля
   ```

2. **Добавить в админ-панель:**
   ```
   /admin → Add Course → Fin-Reboot: 5 лет на $79
   ```

3. **Настроить расписание в n8n:**
   - День 1 → Модуль 1 (тизер)
   - День 2 → Модуль 2 (основной)
   - День 7 → Модуль 3
   - День 14 → Модуль 4 + сертификат

4. **Готово!** Система автоматически:
   - Берёт платежи
   - Выпускает уроки по расписанию
   - Проверяет домашние задания
   - Выдаёт сертификат
   - Предлагает уpsell (консультация, VIP поддержка)

---

## 📱 Telegram Mini Apps (TMA)

Встроенные приложения для интерактивности:

### Инвест-калькулятор
Студент вводит начальный капитал → калькулятор показывает потенциальный результат через 5/10/20 лет.

### Финансовый чекап
Анонимный квиз на определение финансового уровня (новичок/опытный/эксперт) → рекомендация курса.

**Технология:** React + Telegram WebApp SDK → встраивается прямо в Telegram

---

## 🔐 Безопасность

- API ключи только в `.env` (под `.gitignore`)
- Webhook сигнатуры bePaid проверяются (HMAC-SHA256)
- Доступ к курсу проверяется по `student_id` в БД
- Все транзакции логируются
- Нет логирования платёжных данных

---

## 📈 Прибыльность

На примере курса за $79:

```
100 студентов/месяц × $79 = $7,900
Минус: Claude API (~$100), bePaid fees (2%) = ~$260
Чистая прибыль: $7,640/месяц

Участие автора: 0 часов (после запуска)
Масштабируемость: линейная (один курс, бесконечно студентов)
```

---

## 🛠️ Развитие

Возможные расширения:
- Сертификаты на блокчейне (Web3)
- Партнёрская программа (реферальные 20%)
- Group-buy опции (скидка если минимум 5 человек)
- Подписка (курсы + новые модули еженедельно)

---

## 📞 Контакты

- **GitHub Issues:** [создать issue](https://github.com/IDonRumata/Fin-Reboot-Bot/issues)
- **Telegram:** [@DonRumataE](https://t.me/DonRumataE)

---

*EdTech платформа для экспертов, которые хотят масштабировать без найма команды.*
