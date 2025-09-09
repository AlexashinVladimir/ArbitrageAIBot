from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_kb():
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("📚 Курсы")], [KeyboardButton("🛠️ Админ-панель")]],
        resize_keyboard=True
    )
    return kb

def cancel_kb():
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("❌ Отмена")]],
        resize_keyboard=True
    )
    return kb

def category_kb(categories: list):
    kb = InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        kb.add(InlineKeyboardButton(text=cat[1], callback_data=f"user_cat:{cat[0]}"))
    return kb

def course_kb(courses: list):
    kb = InlineKeyboardMarkup(row_width=1)
    for course in courses:
        kb.add(InlineKeyboardButton(text=course[2], callback_data=f"course:{course[0]}"))
    return kb

def pay_kb(course_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("💳 Оплатить", callback_data=f"pay:{course_id}"))
    return kb


