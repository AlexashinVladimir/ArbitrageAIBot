"""
keyboards.py — все клавиатуры для бота.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def main_menu(admin: bool = False):
    buttons = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="ℹ️ О боте")],
    ]
    if admin:
        buttons.append([KeyboardButton(text="⚙️ Админ")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def categories_inline(categories):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}")] for c in categories
        ]
    )
    return kb


def courses_inline(courses):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c["title"], callback_data=f"course_show:{c['id']}")] for c in courses
        ]
    )
    return kb


def course_detail_inline(course):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Купить", callback_data=f"course_pay:{course['payload']}")]
        ]
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Управление категориями")],
            [KeyboardButton(text="Управление курсами")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def admin_categories_inline(categories):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c["title"], callback_data=f"admin_category:{c['id']}")] for c in categories
        ] + [
            [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category")]
        ]
    )
    return kb


def admin_courses_inline(courses):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c["title"], callback_data=f"admin_course:{c['id']}")] for c in courses
        ] + [
            [InlineKeyboardButton(text="➕ Добавить курс", callback_data="admin_add_course")]
        ]
    )
    return kb


def edit_course_inline(course_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Название", callback_data=f"edit_course_title:{course_id}")],
            [InlineKeyboardButton(text="Описание", callback_data=f"edit_course_description:{course_id}")],
            [InlineKeyboardButton(text="Цена", callback_data=f"edit_course_price:{course_id}")],
            [InlineKeyboardButton(text="Ссылка", callback_data=f"edit_course_link:{course_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_course:{course_id}")],
        ]
    )


