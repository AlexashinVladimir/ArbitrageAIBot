"""
keyboards.py — все клавиатуры для бота.
(обновлён: кнопка оплаты теперь сразу показывает цену)
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
        buttons.append([KeyboardButton(text="👑 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Управление категориями")],
        [KeyboardButton(text="Управление курсами")],
        [KeyboardButton(text="❌ Отмена")],
    ],
    resize_keyboard=True
)


def categories_inline(categories: list[dict]):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}")]
            for c in categories
        ]
    )


def categories_admin_inline(categories: list[dict]):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for c in categories:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ {c['title']}", callback_data=f"delcat:{c['id']}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category")])
    return kb


def admin_courses_inline(courses: list[dict]):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for c in courses:
        kb.inline_keyboard.append([InlineKeyboardButton(text=c["title"], callback_data=f"admin_course:{c['id']}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="➕ Добавить курс", callback_data="admin_add_course")])
    return kb


# -------------------------------------
# ОБНОВЛЁННАЯ ФУНКЦИЯ: course_inline
# принимает целый словарь course (с полем 'price' и 'currency'/'link' и т.д.)
# Возвращает InlineKeyboard с одной кнопкой, в тексте которой указана цена.
# -------------------------------------
def course_inline(course: dict):
    # ожидается, что course['price'] — целое число (рубли) или (если копейки) тогда нужно форматировать по-другому
    price_display = f"{course.get('price', 0)}"
    # если в курсе хранится цена в копейках (например 199900) — поменяй формат:
    # price_display = f"{course.get('price', 0)/100:.2f}"
    button_text = f"💳 Оплатить — {price_display} ₽"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button_text, callback_data=f"buy:{course['id']}")]
        ]
    )


def course_admin_inline(course_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"editcourse:{course_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delcourse:{course_id}")]
        ]
    )


edit_course_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Название")],
        [KeyboardButton(text="Описание")],
        [KeyboardButton(text="Цена")],
        [KeyboardButton(text="Ссылка")],
        [KeyboardButton(text="❌ Отмена")],
    ],
    resize_keyboard=True
)





