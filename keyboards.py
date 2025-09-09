from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Главное меню
def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📚 Курсы")],
            [KeyboardButton("💡 Рекомендации ИИ")],
            [KeyboardButton("🛠️ Админ-панель")]
        ],
        resize_keyboard=True
    )

# Кнопка отмены
def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("❌ Отмена")]],
        resize_keyboard=True
    )

# Inline категории
def category_kb(categories):
    kb = InlineKeyboardMarkup(row_width=2)
    if not categories:
        kb.add(InlineKeyboardButton("◀️ В главное меню", callback_data="back_main"))
        return kb
    for cat in categories:
        if cat[2]:
            kb.insert(InlineKeyboardButton(cat[1], callback_data=f"user_cat:{cat[0]}"))
    kb.add(InlineKeyboardButton("◀️ В главное меню", callback_data="back_main"))
    return kb

# Inline курсы
def course_kb(courses):
    kb = InlineKeyboardMarkup(row_width=1)
    if not courses:
        kb.add(InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_categories"))
        return kb
    for course in courses:
        if course[6]:
            kb.add(InlineKeyboardButton(course[2], callback_data=f"course:{course[0]}"))
    kb.add(InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_categories"))
    return kb

# Кнопка оплаты
def pay_kb(course_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Оплатить", callback_data=f"pay:{course_id}"))
    kb.add(InlineKeyboardButton("◀️ Назад к курсам", callback_data="back_categories"))
    return kb

# Админка
def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📂 Управление категориями")],
            [KeyboardButton("📚 Управление курсами")],
            [KeyboardButton("➕ Добавить категорию")],
            [KeyboardButton("➕ Добавить курс")],
            [KeyboardButton("◀️ В главное меню")]
        ],
        resize_keyboard=True
    )

# Управление категориями
def manage_categories_kb(categories):
    kb = InlineKeyboardMarkup(row_width=2)
    if not categories:
        kb.add(InlineKeyboardButton("◀️ Назад", callback_data="back_admin"))
        return kb
    for cat in categories:
        text = f"{cat[1]} {'✅' if cat[2] else '❌'}"
        kb.insert(InlineKeyboardButton(text, callback_data=f"toggle_cat:{cat[0]}"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="back_admin"))
    return kb

# Управление курсами
def manage_courses_kb(courses):
    kb = InlineKeyboardMarkup(row_width=1)
    if not courses:
        kb.add(InlineKeyboardButton("◀️ Назад", callback_data="back_admin"))
        return kb
    for course in courses:
        text = f"{course[2]} {'✅' if course[6] else '❌'}"
        kb.add(InlineKeyboardButton(text, callback_data=f"toggle_course:{course[0]}"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="back_admin"))
    return kb


