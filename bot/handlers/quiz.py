"""Quiz funnel handler - provocative quiz for cold audience segmentation.

Deep link: t.me/bot?start=quiz_instagram → quiz → result → lead magnet → offer.
FSM States: q1..q6, waiting_name, finished.
"""

from __future__ import annotations

import logging

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import settings
from bot.database import repositories as repo

logger = logging.getLogger(__name__)
router = Router(name="quiz")


# ──────────────────────── FSM States ──────────────────────────


class QuizStates(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()
    waiting_name = State()
    finished = State()


# ──────────────────────── Questions ───────────────────────────

QUESTIONS = {
    "q1": {
        "text": (
            "🛋 <b>Вопрос 1 из 6</b>\n\n"
            "Деньги, которые ты откладываешь - где они обычно оседают?"
        ),
        "options": [
            ("A", "Наличка дома - конверт, матрас"),
            ("B", "На карточке - просто лежат"),
            ("C", "На вкладе - хоть что-то капает"),
            ("D", "В разных местах - пробую варианты"),
        ],
    },
    "q2": {
        "text": (
            "💸 <b>Вопрос 2 из 6</b>\n\n"
            "Ты замечаешь, что на ту же зарплату можно купить меньше, "
            "чем год назад. Твоя реакция?"
        ),
        "options": [
            ("A", "Злюсь, но смиряюсь"),
            ("B", "Трачу меньше, больше откладываю"),
            ("C", "Надо бы вложить, но не знаю куда"),
            ("D", "Уже ищу способы защитить деньги"),
        ],
    },
    "q3": {
        "text": (
            "📱 <b>Вопрос 3 из 6</b>\n\n"
            "Друг говорит: «Я начал откладывать по 50 рублей в месяц в акции». "
            "Твоя реакция?"
        ),
        "options": [
            ("A", "Акции - это лотерея, лучше не трогать"),
            ("B", "Интересно, но страшно потерять"),
            ("C", "Нормально, тоже думаю попробовать"),
            ("D", "Маловато - я бы вложил(а) больше"),
        ],
    },
    "q4": {
        "text": (
            "🎯 <b>Вопрос 4 из 6</b>\n\n"
            "Есть ли у тебя конкретная финансовая цель на ближайшие 3 года?"
        ),
        "options": [
            ("A", "Дотянуть до следующей зарплаты"),
            ("B", "Хочу накопить, но конкретики нет"),
            ("C", "Есть примерная сумма-цель"),
            ("D", "Чёткий план: сколько, куда, когда"),
        ],
    },
    "q5": {
        "text": (
            "⏰ <b>Вопрос 5 из 6</b>\n\n"
            "Как часто ты вообще думаешь о своих деньгах "
            "(не считая момент, когда они кончились)?"
        ),
        "options": [
            ("A", "Когда карта зависла на кассе"),
            ("B", "Смотрю выписку - грущу"),
            ("C", "Слежу за расходами, читаю"),
            ("D", "Регулярно анализирую и улучшаю"),
        ],
    },
    "q6": {
        "text": (
            "🔮 <b>Вопрос 6 из 6</b>\n\n"
            "Через 10 лет ты хочешь..."
        ),
        "options": [
            ("A", "Стабильная работа, всё как идёт"),
            ("B", "Подушка безопасности и спокойствие"),
            ("C", "Доп. доход помимо работы"),
            ("D", "Не зависеть от работы вообще"),
        ],
    },
}

# ──────────────────────── Score Map ───────────────────────────

SCORE_MAP = {
    "q1": {"A": 1, "B": 2, "C": 3, "D": 4},
    "q2": {"A": 1, "B": 2, "C": 3, "D": 4},
    "q3": {"A": 1, "B": 2, "C": 3, "D": 4},
    "q4": {"A": 1, "B": 2, "C": 3, "D": 4},
    "q5": {"A": 1, "B": 2, "C": 3, "D": 4},
    "q6": {"A": 1, "B": 2, "C": 3, "D": 4},
}


def _calculate_type(score: int) -> str:
    if score <= 12:
        return "A"
    elif score <= 18:
        return "B"
    else:
        return "C"


# ──────────────────── Result Texts ────────────────────────────

RESULT_TEXTS = {
    "A": (
        "🛡 <b>{name}, ты - Осторожный хранитель</b>\n\n"
        "Ты ценишь стабильность и предсказуемость. "
        "Деньги для тебя - это прежде всего безопасность.\n\n"
        "Это отличное качество! Но есть нюанс: пока деньги «лежат» - "
        "инфляция тихо их съедает. За 5 лет накопления теряют "
        "до 30% покупательной силы.\n\n"
        "💡 <b>Что тебе даст курс:</b>\n"
        "▸ Как создать подушку безопасности без страха\n"
        "▸ Первый шаг в инвестиции - безопасно и понятно\n"
        "▸ Конкретные инструменты, доступные отовсюду\n\n"
        "Даже небольшая сумма в месяц - уже старт. "
        "И ты удивишься, как быстро это начинает работать 💪"
    ),
    "B": (
        "🚀 <b>{name}, ты - Готов к действию</b>\n\n"
        "Ты уже понимаешь, что деньги должны работать. "
        "Интерес есть, знания - частично. "
        "Не хватает одного: системы и конкретных шагов.\n\n"
        "Ты в идеальной точке старта! "
        "Именно такие люди после курса показывают лучшие результаты.\n\n"
        "💡 <b>Что тебе даст курс:</b>\n"
        "▸ Пошаговый план: от нуля до работающего портфеля\n"
        "▸ Открытие счета на бирже и первые покупки\n"
        "▸ Стратегия регулярных вложений - покупай и не парься\n\n"
        "Через 5 дней у тебя будет работающая система, "
        "а не просто желание «когда-нибудь начать» 🎯"
    ),
    "C": (
        "📊 <b>{name}, ты - Инвестор без системы</b>\n\n"
        "Ты уже думаешь о деньгах серьёзно - возможно, "
        "пробовал(а) что-то откладывать или вкладывать. "
        "Но когда спрашиваешь себя «а что дальше?» - "
        "чёткого плана нет.\n\n"
        "Хаотичные действия без стратегии - это не инвестирование, "
        "а угадайка. У тебя есть мотивация, нет структуры.\n\n"
        "💡 <b>Что тебе даст курс:</b>\n"
        "▸ Как собрать диверсифицированный портфель\n"
        "▸ Распределение между разными инструментами\n"
        "▸ Наш личный «ускоритель» - автоматический инструмент\n\n"
        "Системный подход превращает случайные действия "
        "в предсказуемый рост капитала 📈"
    ),
}


# ──────────────── Question state mapping ──────────────────────

QUESTION_ORDER = ["q1", "q2", "q3", "q4", "q5", "q6"]
STATE_MAP = {
    "q1": QuizStates.q1,
    "q2": QuizStates.q2,
    "q3": QuizStates.q3,
    "q4": QuizStates.q4,
    "q5": QuizStates.q5,
    "q6": QuizStates.q6,
}


def _build_question_text(question_key: str) -> str:
    """Build full question text with answer options listed in the message."""
    q = QUESTIONS[question_key]
    options_text = "\n".join(
        f"{letter}) {text}" for letter, text in q["options"]
    )
    return f'{q["text"]}\n\n{options_text}'


def _build_question_keyboard(question_key: str) -> InlineKeyboardMarkup:
    """Build compact inline keyboard with just A/B/C/D buttons in one row."""
    q = QUESTIONS[question_key]
    buttons = [
        InlineKeyboardButton(
            text=option_letter,
            callback_data=f"quiz_{question_key}_{option_letter}",
        )
        for option_letter, _ in q["options"]
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


# ──────────────────── Handlers ────────────────────────────────


async def start_quiz(message: types.Message, state: FSMContext) -> None:
    """Entry point - called from start.py when deep link has quiz_ prefix."""
    # A/B split: assign group based on telegram_id
    ab_group = "A" if (message.from_user.id % 2 == 0) else "B"  # type: ignore[union-attr]
    await state.update_data(ab_group=ab_group)

    if ab_group == "A":
        # Variant A - benefits-focused
        welcome_text = (
            "━━━━━━━━━━━━━━━━━━━\n"
            "🔥 <b>Финансовая перезагрузка</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "Привет! 👋\n\n"
            "Ответь на <b>6 коротких вопросов</b> - "
            "и ты узнаешь свой финансовый тип.\n\n"
            "А ещё получишь:\n"
            "🎁 Шпаргалку по налогам на инвестиции\n"
            "📊 Персональные рекомендации\n\n"
            "Занимает 2 минуты. Погнали? 🚀"
        )
    else:
        # Variant B - loss-aversion focused
        welcome_text = (
            "━━━━━━━━━━━━━━━━━━━\n"
            "💸 <b>Ваши деньги тают. Проверим?</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "Привет! 👋\n\n"
            "Пока вы читаете это сообщение - инфляция "
            "съедает ваши сбережения.\n\n"
            "Ответьте на <b>6 вопросов за 2 минуты</b> - "
            "и узнайте, защищены ли ваши деньги.\n\n"
            "🎁 Бонус: шпаргалка по налогам на инвестиции"
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать квиз!", callback_data="quiz_start")]
        ]
    )
    await message.answer(welcome_text, reply_markup=keyboard)


@router.callback_query(F.data == "quiz_start")
async def quiz_begin(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Start the quiz - send question 1."""
    await callback.answer()
    await state.clear()
    await state.set_state(QuizStates.q1)
    await state.update_data(answers={})

    text = _build_question_text("q1")
    keyboard = _build_question_keyboard("q1")
    if callback.message:
        await callback.message.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]


@router.callback_query(
    QuizStates.q1,
    F.data.startswith("quiz_q1_"),
)
async def process_q1(callback: types.CallbackQuery, state: FSMContext) -> None:
    await _process_answer(callback, state, "q1", "q2", QuizStates.q2)


@router.callback_query(
    QuizStates.q2,
    F.data.startswith("quiz_q2_"),
)
async def process_q2(callback: types.CallbackQuery, state: FSMContext) -> None:
    await _process_answer(callback, state, "q2", "q3", QuizStates.q3)


@router.callback_query(
    QuizStates.q3,
    F.data.startswith("quiz_q3_"),
)
async def process_q3(callback: types.CallbackQuery, state: FSMContext) -> None:
    await _process_answer(callback, state, "q3", "q4", QuizStates.q4)


@router.callback_query(
    QuizStates.q4,
    F.data.startswith("quiz_q4_"),
)
async def process_q4(callback: types.CallbackQuery, state: FSMContext) -> None:
    await _process_answer(callback, state, "q4", "q5", QuizStates.q5)


@router.callback_query(
    QuizStates.q5,
    F.data.startswith("quiz_q5_"),
)
async def process_q5(callback: types.CallbackQuery, state: FSMContext) -> None:
    await _process_answer(callback, state, "q5", "q6", QuizStates.q6)


@router.callback_query(
    QuizStates.q6,
    F.data.startswith("quiz_q6_"),
)
async def process_q6(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Last question - ask for name instead of next question."""
    await callback.answer()
    option = callback.data.split("_")[-1]  # type: ignore[union-attr]

    data = await state.get_data()
    answers = data.get("answers", {})
    answers["q6"] = option
    await state.update_data(answers=answers)

    await state.set_state(QuizStates.waiting_name)

    if callback.message:
        await callback.message.answer(  # type: ignore[union-attr]
            "✍️ Отлично! Последний шаг.\n\n"
            "<b>Как тебя зовут?</b>\n\n"
            "Напиши своё имя - мы персонализируем результат.",
        )


@router.message(QuizStates.waiting_name)
async def process_name(
    message: types.Message, state: FSMContext, session: AsyncSession
) -> None:
    """Receive name, calculate score, show result."""
    if not message.from_user or not message.text:
        return

    name = message.text.strip()[:100]
    data = await state.get_data()
    answers = data.get("answers", {})

    # Calculate score
    total_score = 0
    for q_key, option in answers.items():
        total_score += SCORE_MAP.get(q_key, {}).get(option.upper(), 0)

    user_type = _calculate_type(total_score)

    # Save to DB
    ab_group = data.get("ab_group")
    await repo.save_quiz_result(
        session,
        telegram_id=message.from_user.id,
        answers=answers,
        score=total_score,
        user_type=user_type,
        name=name,
        ab_group=ab_group,
    )

    await state.set_state(QuizStates.finished)

    # Send result
    result_text = RESULT_TEXTS[user_type].format(name=name)
    await message.answer(result_text)

    # Small delay, then lead magnet
    import asyncio
    await asyncio.sleep(2)

    # Lead magnet - tax cheatsheet
    lead_magnet_text = (
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎁 <b>Твой подарок: Шпаргалка по налогам</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Мы подготовили шпаргалки по налогам "
        "на инвестиции для разных стран.\n\n"
        "Выбери свою страну 👇"
    )
    tax_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🇧🇾 Беларусь",
                url="https://docs.google.com/document/d/11naEiD4vSJvzFivYtB_PBpL6JE6Y3hc231tkz6WZQGs/edit?tab=t.0#heading=h.p8axpjuwagqo",
            )],
            [InlineKeyboardButton(
                text="🇷🇺 Россия",
                url="https://docs.google.com/document/d/1zuEgfUV89ndfPAOR8xLbFB1vB0hf5vOUWfT-OW_J_Rs/edit?tab=t.0#heading=h.xkpy0wuymb5s",
            )],
            [InlineKeyboardButton(
                text="🇰🇿 Казахстан",
                url="https://docs.google.com/document/d/1r8r6YXlWfw4xlRYwulDqZ-dskrPK7oUxv9ixguSagOU/edit?tab=t.0#heading=h.k0d6w0cvc7xp",
            )],
            [InlineKeyboardButton(
                text="🇺🇦 Украина",
                url="https://docs.google.com/document/d/1MBZa0vhJdrOuw71Lt854aw34Pfh0BhSOKA3HHgWCLuU/edit?tab=t.0#heading=h.l582nagt5xcn",
            )],
            [InlineKeyboardButton(
                text="🇵🇱 Польша",
                url="https://docs.google.com/document/d/1tDsmIN5-eiLG3RDOH1R9GI6KDLGBvdoCBFjsSMqE_oU/edit?tab=t.0#heading=h.xb43zrl8o7t0",
            )],
        ]
    )
    await message.answer(lead_magnet_text, reply_markup=tax_keyboard)

    await asyncio.sleep(2)

    # Authors block
    authors_text = (
        "👥 <b>Кто стоит за курсом?</b>\n\n"
        "👩 <b>Марина Дементьева</b> - 20 лет в инвестициях, "
        "с 2010 года не работает в найме - живёт на пассивный доход\n"
        '<a href="https://tiktok.com/@dementjeva17">TikTok</a>  '
        '<a href="https://youtube.com/@МаринаДементьева/shorts">YouTube</a>  '
        '<a href="https://instagram.com/marina_dementjeva">Instagram</a>\n\n'
        "👨 <b>Андрей Мороз</b> - дальнобойщик, строит капитал прямо в рейсах\n"
        "С 25 октября 2025 делает +1 отжимание каждый день - "
        "годовой челлендж. Говорит: с деньгами работает то же самое.\n"
        '<a href="https://tiktok.com/@krononchill">TikTok</a>  '
        '<a href="https://youtube.com/@andreimarozv">YouTube</a>  '
        '<a href="https://instagram.com/krononchill">Instagram</a>'
    )
    await message.answer(authors_text, disable_web_page_preview=True)

    await asyncio.sleep(2)

    # Course offer
    offer_text = (
        "━━━━━━━━━━━━━━━━━━━\n"
        "🔥 <b>Курс «Финансовая перезагрузка»</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"{name}, за 5 дней ты:\n\n"
        "📊 Посчитаешь свой финансовый баланс\n"
        "🛡 Создашь подушку безопасности\n"
        "₿ Откроешь криптокошелёк на легальной бирже\n"
        "📈 Откроешь брокерский счёт\n"
        "🏆 Соберёшь свой первый портфель\n\n"
        "Каждый день - одно практическое действие.\n"
        "Автор курса - <b>Марина Дементьева</b>, "
        "20 лет в инвестициях, с 2010 года живёт на пассивный доход.\n\n"
        "💰 Стоимость: <b>15 BYN</b>\n\n"
        "Это меньше, чем одна поездка на такси. "
        "А результат - на всю жизнь."
    )
    offer_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="💳 Купить курс за 15 BYN",
                callback_data="buy",
            )],
            [InlineKeyboardButton(
                text="📋 Подробнее о программе",
                callback_data="about",
            )],
            [InlineKeyboardButton(
                text="⏳ Подумаю",
                callback_data="quiz_later",
            )],
        ]
    )
    await message.answer(offer_text, reply_markup=offer_keyboard)

    await state.clear()


@router.callback_query(F.data == "quiz_later")
async def quiz_later(callback: types.CallbackQuery) -> None:
    """User chose to think about it - friendly message."""
    await callback.answer()
    text = (
        "Без проблем! 😊\n\n"
        "Когда будешь готов(а) - просто напиши /start "
        "и нажми «Купить курс».\n\n"
        "А пока шпаргалка по налогам - твоя. "
        "Пользуйся! 🎁"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Открыть меню", callback_data="menu")],
        ]
    )
    if callback.message:
        await callback.message.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]


async def _process_answer(
    callback: types.CallbackQuery,
    state: FSMContext,
    current_q: str,
    next_q: str,
    next_state: State,
) -> None:
    """Generic handler: save answer, send next question."""
    await callback.answer()
    option = callback.data.split("_")[-1]  # type: ignore[union-attr]

    data = await state.get_data()
    answers = data.get("answers", {})
    answers[current_q] = option
    await state.update_data(answers=answers)

    await state.set_state(next_state)

    text = _build_question_text(next_q)
    keyboard = _build_question_keyboard(next_q)
    if callback.message:
        await callback.message.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]
