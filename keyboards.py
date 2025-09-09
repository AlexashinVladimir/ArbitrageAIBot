from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- Главное меню ---
def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Курсы")],
            [KeyboardButton(text="💡 Рекомендации ИИ")],
            [KeyboardButton(text="🛠️ Админ-панель")]
        ],
        resize_keyboard=True
    )

# --- Админ-панель ---
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

# --- Inline кнопки категорий ---
def category_kb(categories: list):
    kb = InlineKeyboardMarkup(row_width=1)
    for cat_id, name, is_active in categories:
        kb.add(InlineKeyboardButton(text=f"{name}", callback_data=f"category:{cat_id}"))
    return kb

# --- Inline кнопки курсов ---
def course_kb(courses: list):
    kb = InlineKeyboardMarkup(row_width=1)
    for course in courses:
        kb.add(
            InlineKeyboardButton(text=f"{course[1]} - {course[3]} ₽", callback_data=f"course:{course[0]}")
        )
    return kb

# --- Кнопка оплаты ---
def pay_kb(course_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(text="💳 Оплатить курс", callback_data=f"pay:{course_id}")
    )
    return kb

# --- Управление категориями ---
def manage_categories_kb(categories: list):
    kb = InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        status = "✅" if cat[2] else "❌"
        kb.add(InlineKeyboardButton(text=f"{cat[1]} {status}", callback_data=f"toggle_cat:{cat[0]}"))
    return kb

# --- Управление курсами ---
def manage_courses_kb(courses: list):
    kb = InlineKeyboardMarkup(row_width=1)
    for course in courses:
        status = "✅" if course[5] else "❌"
        kb.add(InlineKeyboardButton(text=f"{course[1]} {status}", callback_data=f"toggle_course:{course[0]}"))
    return kb



