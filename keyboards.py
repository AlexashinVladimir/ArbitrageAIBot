from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

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

# Кнопка отмены / выхода
def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

# Inline категории
def category_kb(categories):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if not categories:
        kb.add(InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_main"))
        return kb
    for cat in categories:
        if cat[2]:
            kb.add(InlineKeyboardButton(text=cat[1], callback_data=f"user_cat:{cat[0]}"))
    kb.add(InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_main"))
    return kb

# Inline курсы
def course_kb(courses):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if not courses:
        kb.add(InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="back_categories"))
        return kb
    for course in courses:
        if course[6]:
            kb.add(InlineKeyboardButton(text=course[2], callback_data=f"course:{course[0]}"))
    kb.add(InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="back_categories"))
    return kb

# Кнопка оплаты
def pay_kb(course_id):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.add(InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay:{course_id}"))
    kb.add(InlineKeyboardButton(text="◀️ Назад к курсам", callback_data="back_categories"))
    return kb

# Админка
def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📂 Управление категориями")],
            [KeyboardButton(text="📚 Управление курсами")],
            [KeyboardButton(text="➕ Добавить категорию")],
            [KeyboardButton(text="➕ Добавить курс")],
            [KeyboardButton(text="◀️ В главное меню")]
        ],
        resize_keyboard=True
    )



