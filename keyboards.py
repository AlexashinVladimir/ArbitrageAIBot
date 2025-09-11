from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# Главное меню
def main_menu(is_admin: bool = False):
    kb = [
        [KeyboardButton(text="📚 Категории")],
        [KeyboardButton(text="ℹ️ О боте")],
    ]
    if is_admin:
        kb.append([KeyboardButton(text="⚙️ Админ панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# Админ панель
def admin_menu():
    kb = [
        [KeyboardButton(text="➕ Добавить категорию")],
        [KeyboardButton(text="➕ Добавить курс")],
        [KeyboardButton(text="🗂 Управление категориями")],
        [KeyboardButton(text="🎓 Управление курсами")],
        [KeyboardButton(text="⬅️ Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# Кнопка отмены
def cancel_kb():
    kb = [[KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# Список категорий (для пользователя)
def categories_inline(categories: list):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cat["name"], callback_data=f"cat_{cat['id']}")]
            for cat in categories
        ]
    )
    return kb


# Список курсов в категории
def courses_inline(courses: list):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{c['title']} — {c['price']} ₽", callback_data=f"course_{c['id']}")]
            for c in courses
        ]
    )
    return kb


# Управление категориями (админ)
def manage_categories_inline(categories: list):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ {cat['name']}", callback_data=f"delcat_{cat['id']}")]
            for cat in categories
        ]
    )
    return kb


# Управление курсами (админ)
def manage_courses_inline(courses: list):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ {c['title']}", callback_data=f"delcourse_{c['id']}")]
            for c in courses
        ]
    )
    return kb


# Кнопка оплаты
def buy_course_inline(course_id: int, price: int):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {price} ₽", callback_data=f"buy_{course_id}")]
        ]
    )
    return kb









