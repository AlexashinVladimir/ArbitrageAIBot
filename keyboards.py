from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- Главное меню пользователя ---
def main_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📚 Курсы"))
    kb.add(KeyboardButton("💡 Рекомендации ИИ"))
    kb.add(KeyboardButton("🛠️ Админ-панель"))
    return kb

# --- Кнопки категорий ---
def category_kb(categories: list):
    kb = InlineKeyboardMarkup(row_width=1)
    for cat_id, name, is_active in categories:
        kb.add(InlineKeyboardButton(text=f"{name}", callback_data=f"category:{cat_id}"))
    return kb

# --- Кнопки курсов ---
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

# --- Админ-панель ---
def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("➕ Добавить категорию"))
    kb.add(KeyboardButton("📂 Управление категориями"))
    kb.add(KeyboardButton("➕ Добавить курс"))
    kb.add(KeyboardButton("📚 Управление курсами"))
    kb.add(KeyboardButton("◀️ В главное меню"))
    return kb

# --- Админ управление категориями ---
def manage_categories_kb(categories: list):
    kb = InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        status = "✅" if cat[2] else "❌"
        kb.add(
            InlineKeyboardButton(text=f"{cat[1]} {status}", callback_data=f"toggle_cat:{cat[0]}")
        )
    return kb

# --- Админ управление курсами ---
def manage_courses_kb(courses: list):
    kb = InlineKeyboardMarkup(row_width=1)
    for course in courses:
        status = "✅" if course[5] else "❌"
        kb.add(
            InlineKeyboardButton(text=f"{course[1]} {status}", callback_data=f"toggle_course:{course[0]}")
        )
    return kb

