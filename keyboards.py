"""
keyboards.py — все клавиатуры для бота.
Совместимо с Aiogram 3.6+
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# -------------------- Главное меню --------------------
def main_menu(admin: bool = False):
    buttons = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="ℹ️ О боте")],
    ]
    if admin:
        buttons.append([KeyboardButton(text="⚙️ Админ")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# -------------------- Админ меню --------------------
def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Управление курсами")],
            [KeyboardButton(text="Управление категориями")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


# -------------------- Категории --------------------
def categories_inline(categories: list[dict]):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}")]
            for c in categories
        ]
    )


def admin_categories_inline(categories: list[dict]):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ {c['title']}", callback_data=f"admin_del_category:{c['id']}")]
            for c in categories
        ]
        + [[InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category")]]
    )


# -------------------- Курсы --------------------
def courses_inline(courses: list[dict]):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=course["title"], callback_data=f"course_show:{course['id']}")]
            for course in courses
        ]
    )


def course_detail_inline(course: dict):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"Оплатить {course['price'] / 100:.2f} {course['currency']}",
                callback_data=f"course_pay:{course['payload']}"
            )]
        ]
    )


def admin_courses_inline(courses: list[dict]):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✏️ {c['title']}", callback_data=f"admin_course:{c['id']}")]
            for c in courses
        ]
        + [[InlineKeyboardButton(text="➕ Добавить курс", callback_data="admin_add_course")]]
    )


def edit_course_inline(course_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Название", callback_data=f"edit_course_title:{course_id}")],
            [InlineKeyboardButton(text="Описание", callback_data=f"edit_course_description:{course_id}")],
            [InlineKeyboardButton(text="Цена", callback_data=f"edit_course_price:{course_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_course:{course_id}")],
        ]
    )

