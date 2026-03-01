"""Menu, About, Support handlers."""

from __future__ import annotations

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.core.config import settings

router = Router(name="menu")


MENU_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💰 Купить курс", callback_data="buy")],
        [InlineKeyboardButton(text="📋 О программе", callback_data="about")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="progress")],
        [InlineKeyboardButton(
            text="🧮 Калькулятор инвестора",
            url=settings.webapp_calc_url,
        )],
        [InlineKeyboardButton(
            text="📉 Финансовый рентген",
            url=settings.webapp_tracker_url,
        )],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="📜 Оферта", callback_data="oferta")],
    ]
)


@router.message(Command("menu"))
@router.message(F.text.casefold() == "меню")
async def cmd_menu(message: types.Message) -> None:
    await message.answer(
        "📱 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=MENU_KEYBOARD,
    )


@router.callback_query(F.data == "menu")
async def cb_menu(callback: types.CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(  # type: ignore[union-attr]
            "📱 <b>Главное меню</b>\n\nВыберите действие:",
            reply_markup=MENU_KEYBOARD,
        )


ABOUT_TEXT = (
    "━━━━━━━━━━━━━━━━━━━\n"
    "📋 <b>О программе</b>\n"
    "━━━━━━━━━━━━━━━━━━━\n\n"
    "«Финансовая перезагрузка» – 5-дневный практический курс.\n\n"
    "📊 <b>День 1:</b> Снимаем розовые очки – финансовый рентген\n"
    "🛡 <b>День 2:</b> Стратегия защиты денег – подушка + сложный процент\n"
    "₿ <b>День 3:</b> Открываем криптокошелёк\n"
    "📈 <b>День 4:</b> Открываем брокерский счёт\n"
    "🏆 <b>День 5:</b> Собираем портфель + ускоритель капитала\n\n"
    "Каждый день – одно практическое действие.\n"
    "Между днями – 24 часа для выполнения задания."
)


@router.callback_query(F.data == "about")
async def cb_about(callback: types.CallbackQuery) -> None:
    await callback.answer()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Купить курс", callback_data="buy")],
            [InlineKeyboardButton(text="🔙 Меню", callback_data="menu")],
        ]
    )
    if callback.message:
        await callback.message.answer(ABOUT_TEXT, reply_markup=keyboard)  # type: ignore[union-attr]


@router.callback_query(F.data == "support")
async def cb_support(callback: types.CallbackQuery) -> None:
    await callback.answer()
    text = (
        "🆘 <b>Поддержка</b>\n\n"
        f"Напишите нашему специалисту: {settings.support_username}\n\n"
        "Мы поможем разобраться с любым вопросом!"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Меню", callback_data="menu")],
        ]
    )
    if callback.message:
        await callback.message.answer(text, reply_markup=keyboard)  # type: ignore[union-attr]
