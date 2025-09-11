# keyboards.py
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def main_menu(is_admin: bool = False):
    kb = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="ℹ️ О боте")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def admin_menu():
    kb = [
        [KeyboardButton(text="➕ Добавить категорию"), KeyboardButton(text="📂 Управление категориями")],
        [KeyboardButton(text="➕ Добавить курс"), KeyboardButton(text="📘 Управление курсами")],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def back_to_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)


def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)


def categories_inline(categories):
    buttons = [[InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}")] for c in categories]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def courses_inline(courses):
    buttons = [
        [InlineKeyboardButton(text=f"💳 Купить ({int(c.get('price',0))} ₽)", callback_data=f"buy:{c['id']}")]
        for c in courses
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_delete_inline(entity: str, items):
    """
    entity: 'category' or 'course'
    items: list of dicts with id/title
    """
    buttons = []
    for it in items:
        title = it.get("title") or it.get("name") or it.get("title") or ""
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {title}", callback_data=f"edit_{entity}:{it['id']}"),
            InlineKeyboardButton(text=f"🗑 {title}", callback_data=f"delete_{entity}:{it['id']}")
        ])
    # add back
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)








