# GraFin Video Pipeline: анализ и план реализации

## 1. Исследование: что возможно, а что нет

### Telegram (@roboowner) — ПОЛНОСТЬЮ АВТОМАТИЗИРУЕМО
- Бот уже публикует в канал через Telegram Bot API
- n8n имеет встроенный Telegram-нод
- Ограничения: 30 сообщений/секунду, 20 сообщений/минуту в группу — для нас несущественно
- **Статус: работает, доработок не нужно**

### TikTok — АВТОМАТИЗИРУЕМО ЧЕРЕЗ ПОСРЕДНИКА
- **Нативного TikTok-нода в n8n НЕТ** (community node есть, но нестабильный)
- TikTok Content Posting API требует:
  - Регистрации приложения на developers.tiktok.com
  - OAuth 2.0 авторизации пользователя
  - Прохождения аудита приложения (без аудита видео публикуются как private)
  - Multi-step upload: init → upload chunks → publish → poll status
- **Рабочие решения:**
  1. **Upload-Post.com** — REST API, один вызов для публикации. Есть n8n community node. Платный сервис.
  2. **Blotato** — аналогичный сервис с n8n community node. Поддерживает 9+ платформ.
  3. **Прямой API** — возможно через HTTP Request ноды, но сложная настройка OAuth + chunked upload
- **Рекомендация: Upload-Post.com** — проще всего, один HTTP запрос

### Instagram Reels — АВТОМАТИЗИРУЕМО ЧЕРЕЗ ПОСРЕДНИКА
- Instagram Graph API поддерживает публикацию Reels (с 2022 года)
- **Требования:**
  - Instagram Business или Creator аккаунт
  - Привязанная Facebook Page (обязательно!)
  - Facebook App с разрешениями instagram_content_publish
  - OAuth 2.0 + long-lived token
- **Лимиты:** 50 публикаций/24 часа, 200 API запросов/час
- **Процесс через прямой API:**
  1. POST /media — создать контейнер (media_type=REELS, video_url=...)
  2. Подождать обработку (polling)
  3. POST /media_publish — опубликовать
- **Рабочие решения:** те же Upload-Post.com или Blotato — один вызов вместо трёх
- **Рекомендация: Upload-Post.com** (один сервис на все платформы)

### YouTube Shorts — АВТОМАТИЗИРУЕМО
- Отдельного API для Shorts нет — используется стандартный YouTube Data API v3
- Видео автоматически классифицируется как Short если:
  - Вертикальный формат (9:16)
  - Длительность до 60 секунд
  - В заголовке/описании есть #Shorts
- **Требования:**
  - Google Cloud Project с YouTube Data API v3
  - OAuth 2.0 (refresh token)
  - Квота: ~10,000 единиц/день, один upload = ~1,600 единиц (~6 загрузок/день)
- **n8n:** встроенный YouTube нод поддерживает upload
- **Рекомендация:** можно через нативный YouTube нод n8n ИЛИ через Upload-Post.com

### Генерация видео — АВТОМАТИЗИРУЕМО
- **HeyGen** ($29/мес Creator план, 15 видео/мес):
  - REST API: отправляешь скрипт + avatar_id → получаешь видео через 3-5 минут
  - n8n: HTTP Request нод для вызова + Wait + Poll для ожидания результата
  - Уже запланирован в AUTOMATION_MASTER_PLAN.md
- **Creatomate** (альтернатива):
  - Шаблоны видео + API рендеринга
  - Хорош для text-on-video формата (субтитры, анимация текста)
  - Есть нативный n8n нод
- **ElevenLabs** (клон голоса):
  - API для генерации аудио из текста
  - Бесплатно 10k символов/мес, $5/мес для больше
- **Рекомендация: HeyGen** для аватара, или **Creatomate + ElevenLabs** для формата "текст + голос"

---

## 2. Реалистичная архитектура (фазы внедрения)

### Фаза 1 (сейчас): Telegram + ручная публикация остального
```
n8n Schedule → Python Generator → Telegram ревью → @roboowner
                                                  → JSON файл для ручной публикации
```
- Работает с текущим кодом
- Доработка: добавить webhook из Python бота в n8n

### Фаза 2 (+1-2 недели): HeyGen видео
```
Фаза 1 + кнопка "Создать видео" → HeyGen API → видео на ревью
```
- Нужно: аккаунт HeyGen ($29/мес), загрузить видео для аватара
- n8n: HTTP Request → Poll → отправить ссылку

### Фаза 3 (+2-4 недели): кросс-платформенная публикация
```
Фаза 2 + Upload-Post.com → TikTok + Instagram Reels + YouTube Shorts
```
- Нужно: аккаунт Upload-Post.com, подключить соц.сети
- Нужно: Instagram Business + Facebook Page
- Нужно: TikTok аккаунт
- Нужно: YouTube канал

---

## 3. Ограничения API платформ

| Платформа | Лимит публикаций | OAuth | Особенности |
|---|---|---|---|
| Telegram | 30 msg/sec | Bot Token | Проще всего |
| TikTok | ~50/день | OAuth 2.0 + аудит | Без аудита = private видео |
| Instagram | 50/24ч | OAuth 2.0 + FB Page | Обязательна привязка к Facebook |
| YouTube | ~6 uploads/день (квота) | OAuth 2.0 | Shorts = обычный upload, вертикальный формат |

---

## 4. Стоимость автоматизации

| Сервис | Цена | Что даёт |
|---|---|---|
| n8n (self-hosted) | $0 | Оркестрация |
| Gemini 2.5 Flash | $0 (free tier) | Генерация текста |
| HeyGen Creator | $29/мес | 15 видео/мес с аватаром |
| Upload-Post.com | ~$10-20/мес | Кросс-платформенная публикация |
| ElevenLabs | $0-5/мес | Клон голоса |
| **Итого** | **~$39-54/мес** | |

---

## 5. Что нужно сделать для запуска

### Немедленно (Фаза 1):
1. Импортировать `05_grafin_video_pipeline.json` в n8n
2. Настроить переменную `ANDREY_TELEGRAM_ID` в n8n
3. Настроить credential "GraFin Writer Bot" (токен @grafinwriter_bot)
4. Добавить в Python бот отправку POST на webhook при нажатии кнопок одобрения
5. Запустить Python API-сервер: `uvicorn api:app --port 8000` (или добавить endpoint `/generate` в существующий бот)

### Для Фазы 2 (видео):
1. Зарегистрироваться на heygen.com (Creator план)
2. Записать 2-3 мин видео Андрея → загрузить в HeyGen → получить avatar_id
3. Добавить HEYGEN_API_KEY, HEYGEN_AVATAR_ID, HEYGEN_VOICE_ID в n8n Variables

### Для Фазы 3 (все платформы):
1. Зарегистрироваться на upload-post.com
2. Подключить TikTok, Instagram (Business!), YouTube аккаунты
3. Добавить UPLOAD_POST_API_KEY в n8n Variables
4. Убедиться что Instagram привязан к Facebook Page

---

## 6. Альтернативный подход (без Upload-Post.com)

Если не хочется платить за Upload-Post, можно использовать прямые API через HTTP Request ноды n8n:

**YouTube** — реалистично, нативный YouTube нод в n8n.

**Instagram** — реалистично но сложнее:
- Создать Facebook App
- Получить long-lived token
- 3 HTTP запроса: create container → poll → publish

**TikTok** — самое сложное:
- Зарегистрировать TikTok Developer App
- Пройти аудит (иначе видео будут private)
- Сложный multi-step upload

**Вывод:** Upload-Post.com за $10-20/мес экономит десятки часов настройки и поддержки.
