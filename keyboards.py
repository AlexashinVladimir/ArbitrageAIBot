# keyboards.py
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# Главное меню (показывает кнопку "Админ" только админу)
def main_menu(admin: bool = False):
    buttons = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="ℹ️ О боте")],
    ]
    if admin:
        buttons.append([KeyboardButton(text="⚙️ Админ")])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


# Инлайн-клавиатура со списком категорий
def categories_inline(categories):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c["title"], callback_data=f"category_{c['id']}")]
            for c in categories
        ]
    )
    return keyboard


# Инлайн-клавиатура для конкретного курса (с оплатой)
def course_inline(course):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"💳 Оплатить {course['price']} ₽",
                    callback_data=f"buy_{course['id']}"
                )
            ]
        ]
    )
    return keyboard


# Главное меню админа
admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📂 Управление курсами")],
        [KeyboardButton(text="➕ Добавить курс")],
        [KeyboardButton(text="📂 Управление категориями")],
        [KeyboardButton(text="➕ Добавить категорию")],
        [KeyboardButton(text="❌ Отмена")],
    ],
    resize_keyboard=True
)


# Инлайн-список категорий для админа
def categories_admin_inline(categories):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c["title"], callback_data=f"admin_category_{c['id']}")]
            for c in categories
        ]
    )
    return keyboard


# Инлайн-список курсов для админа
def admin_courses_inline(courses):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c["title"], callback_data=f"admin_course_{c['id']}")]
            for c in courses
        ]
    )
    return keyboard


# Инлайн-меню управления курсом (редактировать/удалить)
def course_admin_inline(course_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏ Редактировать", callback_data=f"edit_course_{course_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_course_{course_id}")],
        ]
    )
    return keyboard


# Клавиатура "Отмена"
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)







