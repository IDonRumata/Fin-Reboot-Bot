# План реализации: Квиз-модуль для бота «Финансовая перезагрузка»

## Обзор
Добавить квиз-воронку в существующий бот: 6 вопросов → имя → результат (тип A/B/C) → лид-магнит → оффер курса 15 BYN → дожимная цепочка (3 сообщения).

Deep link: `t.me/bot?start=quiz_instagram` → сохраняет utm_source = `quiz_instagram`.

---

## Файлы для изменения/создания

### 1. `bot/database/models.py` — добавить квиз-поля в User
Добавить к модели `User`:
```
quiz_answers: JSON (nullable)         — {"q1":"a","q2":"c",...}
quiz_score: Integer (nullable)        — итоговый балл
quiz_user_type: String(1) (nullable)  — "A" / "B" / "C"
quiz_name_entered: String(255)        — имя, введённое вручную
quiz_completed_at: DateTime (nullable)
quiz_followup_step: Integer (default=0) — 0=не начат, 1/2/3=шаг дожима
quiz_followup_last_at: DateTime (nullable) — когда отправлен последний дожим
```
Не создаём отдельную таблицу — это 1:1 с пользователем, проще добавить колонки.

### 2. `bot/handlers/quiz.py` — НОВЫЙ ФАЙЛ (основная логика)
- FSM StatesGroup `QuizStates` (q1..q6, waiting_name, finished)
- Константы: `QUESTIONS`, `SCORE_MAP`, `RESULT_TEXTS`
- Handlers:
  - `start_quiz` — приветствие + кнопка «Начать квиз»
  - `quiz_begin` — callback `quiz_start` → отправить вопрос 1, поставить state q1
  - `quiz_answer_q1..q6` — callback `quiz_X_Y` → сохранить ответ, отправить следующий вопрос
  - `quiz_ask_name` — после q6, запросить имя (state waiting_name)
  - `quiz_receive_name` — message handler в state waiting_name → подсчёт баллов → результат
  - `quiz_show_result` — определить тип, отправить персонализированный результат
  - `send_lead_magnet` — текстовый блок «Шпаргалка по налогам»
  - `send_course_offer` — оффер курса 15 BYN + кнопки
  - callback `quiz_buy` → переход на оплату (reuse существующий buy flow)

### 3. `bot/handlers/start.py` — модификация
- Если deep link начинается с `quiz_` → сохранить utm_source и перенаправить в `start_quiz`
- Обычный /start без quiz_ → как сейчас (показать меню)

### 4. `bot/workers/quiz_followup.py` — НОВЫЙ ФАЙЛ
- Функция `check_and_send_quiz_followups(bot)` — планировщик
- Логика:
  - Найти пользователей с `quiz_completed_at IS NOT NULL` и `payment_status != paid`
  - step=0 и прошло ≥1 час → отправить сообщение 1, step=1
  - step=1 и прошло ≥24 часа → отправить сообщение 2, step=2
  - step=2 и прошло ≥72 часа → отправить сообщение 3, step=3
  - step=3 → больше не трогаем

### 5. `bot/database/repositories.py` — добавить квиз-функции
- `save_quiz_result(session, user_id, answers, score, user_type, name)`
- `get_quiz_followup_users(session)` — для планировщика
- `update_followup_step(session, user_id, step)`

### 6. `bot/handlers/admin.py` — расширить команды
- `/stats` — добавить: квиз пройден X, типы A/B/C, конверсия квиз→покупка
- `/export` — НОВАЯ команда: выгрузка CSV (telegram_id, username, name, type, score, utm, purchased)
- `/broadcast [текст]` — НОВАЯ команда: рассылка всем прошедшим квиз

### 7. `bot/main.py` — подключить новые модули
- Импорт и include quiz.router (ПЕРЕД start.router!)
- Добавить job для quiz_followup в scheduler (каждые 30 минут)

---

## Порядок реализации

1. models.py — добавить поля
2. repositories.py — добавить квиз-функции
3. quiz.py — создать хэндлер квиза (FSM + вопросы + результаты + лид-магнит + оффер)
4. start.py — маршрутизация quiz_ deep link
5. quiz_followup.py — воркер дожимной цепочки
6. admin.py — /stats расширение, /export, /broadcast
7. main.py — подключить всё
