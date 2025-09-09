from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📚 Курсы")],
            [KeyboardButton("💡 Рекомендации ИИ")],
            [KeyboardButton("🛠️ Админ-панель")]
        ],
        resize_keyboard=True
    )

def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("❌ Отмена")]],
        resize_keyboard=True
    )

def category_kb(categories):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if not categories:
        kb.add(InlineKeyboardButton("◀️ В главное меню", callback_data="back_main"))
        return kb
    for cat in categories:
        if cat[2]:
            kb.add(InlineKeyboardButton(cat[1], callback_data=f"user_cat:{cat[0]}"))
    kb.add(InlineKeyboardButton("◀️ В главное меню", callback_data="back_main"))
    return kb

def course_kb(courses):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if not courses:
        kb.add(InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_categories"))
        return kb
    for course in courses:
        if course[6]:
            kb.add(InlineKeyboardButton(course[2], callback_data=f"course:{course[0]}"))
    kb.add(InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_categories"))
    return kb

def pay_kb(course_id):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.add(InlineKeyboardButton("💳 Оплатить", callback_data=f"pay:{course_id}"))
    kb.add(InlineKeyboardButton("◀️ Назад к курсам", callback_data="back_categories"))
    return kb

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

def admin_categories_kb(categories):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in categories:
        kb.add(InlineKeyboardButton(f"{cat[1]} {'✅' if cat[2] else '❌'}", callback_data=f"toggle_cat:{cat[0]}"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="back_admin"))
    return kb

def admin_courses_kb(courses):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for c in courses:
        kb.add(InlineKeyboardButton(f"{c[2]} {'✅' if c[6] else '❌'}", callback_data=f"toggle_course:{c[0]}"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="back_admin"))
    return kb



