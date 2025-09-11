from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


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
        [KeyboardButton(text="➕ Добавить категорию")],
        [KeyboardButton(text="📂 Управление категориями")],
        [KeyboardButton(text="➕ Добавить курс")],
        [KeyboardButton(text="📘 Управление курсами")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


def back_to_admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )


def categories_inline(categories: list):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}")]
            for c in categories
        ]
    )


def courses_inline(courses: list):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Купить ({c['price']} ₽)", callback_data=f"buy:{c['id']}")]
            for c in courses
        ]
    )


def edit_delete_inline(entity: str, items: list):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"✏️ {i['title']}", callback_data=f"edit_{entity}:{i['id']}"),
                InlineKeyboardButton(text=f"🗑 {i['title']}", callback_data=f"delete_{entity}:{i['id']}")
            ]
            for i in items
        ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]]
    )









