from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Главное меню
def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Курсы")],
            [KeyboardButton(text="💡 Рекомендации ИИ")],
            [KeyboardButton(text="🛠️ Админ-панель")]
        ],
        resize_keyboard=True
    )

# Админ-панель
def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить категорию")],
            [KeyboardButton(text="📂 Управление категориями")],
            [KeyboardButton(text="➕ Добавить курс")],
            [KeyboardButton(text="📚 Управление курсами")],
            [KeyboardButton(text="◀️ В главное меню")]
        ],
        resize_keyboard=True
    )

# Inline кнопки категорий
def category_kb(categories: list):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"category:{cat_id}")] for cat_id, name, is_active in categories if is_active
        ]
    )

# Inline кнопки курсов
def course_kb(courses: list):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{c[2]} - {c[4]} ₽", callback_data=f"course:{c[0]}")] for c in courses if c[6]
        ]
    )

# Кнопка оплаты
def pay_kb(course_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить курс", callback_data=f"pay:{course_id}")]
        ]
    )

# Управление категориями
def manage_categories_kb(categories: list):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{c[1]} {'✅' if c[2] else '❌'}", callback_data=f"toggle_cat:{c[0]}")] for c in categories
        ]
    )

# Управление курсами
def manage_courses_kb(courses: list):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{c[2]} {'✅' if c[6] else '❌'}", callback_data=f"toggle_course:{c[0]}")] for c in courses
        ]
    )



