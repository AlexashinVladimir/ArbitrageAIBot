# keyboards.py
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


# Главное меню для обычных пользователей
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Категории")],
    ],
    resize_keyboard=True
)


# Главное меню для админа
admin_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Категории")],
        [KeyboardButton(text="⚙️ Админ панель")],
    ],
    resize_keyboard=True
)


# Админ панель
admin_panel_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить категорию")],
        [KeyboardButton(text="➕ Добавить курс")],
        [KeyboardButton(text="📂 Управление курсами")],
        [KeyboardButton(text="⬅️ В меню")],
    ],
    resize_keyboard=True
)


# Клавиатура выбора категории при добавлении курса
def choose_category_kb(categories):
    buttons = [[KeyboardButton(text=c["title"])] for c in categories]
    return ReplyKeyboardMarkup(
        keyboard=buttons + [[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


# Клавиатура с кнопкой "Назад"
back_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ В меню")]],
    resize_keyboard=True
)


# Инлайн-клавиатура для покупки курса
def buy_kb(price: int, course_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Оплатить {price}₽",
                callback_data=f"buy:{course_id}"
            )]
        ]
    )


# Инлайн-клавиатура для управления курсом (редактирование/удаление)
def course_manage_kb(course_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{course_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{course_id}")],
        ]
    )






