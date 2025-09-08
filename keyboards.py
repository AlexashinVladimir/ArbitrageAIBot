from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Главное меню
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Покажи свои артефакты")],
        [KeyboardButton(text="ℹ️ Объясни, как ты работаешь")]
    ],
    resize_keyboard=True
)

# Админ меню
admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить курс"), KeyboardButton(text="🗑 Удалить курс")],
        [KeyboardButton(text="📂 Список курсов"), KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

# Кнопки для курсов
def course_kb(course_id: int):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оплатить и перестать быть статистом", callback_data=f"buy:{course_id}")],
            [InlineKeyboardButton(text="🔙 Вернуться", callback_data="back")]
        ]
    )
    return kb

# Админская кнопка для конкретного курса
def admin_course_kb(course_id: int):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"del:{course_id}")]
        ]
    )
    return kb
