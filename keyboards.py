from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Главное меню
def main_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📚 Курсы"))
    kb.add(KeyboardButton("💡 Рекомендации ИИ"))
    kb.add(KeyboardButton("🛠️ Админ-панель"))
    return kb

# Inline клавиатура категорий для пользователя
def category_kb(categories):
    kb = InlineKeyboardMarkup(row_width=2)
    if not categories:
        kb.add(InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_main"))
        return kb
    for cat in categories:
        if cat[2]:
            kb.insert(InlineKeyboardButton(text=cat[1], callback_data=f"user_cat:{cat[0]}"))
    kb.add(InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_main"))
    return kb

# Inline клавиатура курсов
def course_kb(courses):
    kb = InlineKeyboardMarkup(row_width=1)
    if not courses:
        kb.add(InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="back_categories"))
        return kb
    for course in courses:
        if course[6]:
            kb.add(InlineKeyboardButton(text=course[2], callback_data=f"course:{course[0]}"))
    kb.add(InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="back_categories"))
    return kb

# Inline кнопка оплаты
def pay_kb(course_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay:{course_id}"))
    kb.add(InlineKeyboardButton(text="◀️ Назад к курсам", callback_data="back_categories"))
    return kb

# Админка
def admin_kb():
    kb_r = ReplyKeyboardMarkup(resize_keyboard=True)
    kb_r.add(KeyboardButton("📂 Управление категориями"))
    kb_r.add(KeyboardButton("📚 Управление курсами"))
    kb_r.add(KeyboardButton("➕ Добавить категорию"))
    kb_r.add(KeyboardButton("➕ Добавить курс"))
    kb_r.add(KeyboardButton("◀️ В главное меню"))
    return kb_r

# Управление категориями (админ)
def manage_categories_kb(categories):
    kb_r = InlineKeyboardMarkup(row_width=2)
    if not categories:
        kb_r.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_admin"))
        return kb_r
    for cat in categories:
        text = f"{cat[1]} {'✅' if cat[2] else '❌'}"
        kb_r.insert(InlineKeyboardButton(text=text, callback_data=f"toggle_cat:{cat[0]}"))
    kb_r.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_admin"))
    return kb_r

# Управление курсами (админ)
def manage_courses_kb(courses):
    kb_r = InlineKeyboardMarkup(row_width=1)
    if not courses:
        kb_r.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_admin"))
        return kb_r
    for course in courses:
        text = f"{course[2]} {'✅' if course[6] else '❌'}"
        kb_r.add(InlineKeyboardButton(text=text, callback_data=f"toggle_course:{course[0]}"))
    kb_r.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_admin"))
    return kb_r

# Кнопка выхода из FSM
def cancel_kb():
    kb_r = ReplyKeyboardMarkup(resize_keyboard=True)
    kb_r.add(KeyboardButton("❌ Отмена"))
    return kb_r

