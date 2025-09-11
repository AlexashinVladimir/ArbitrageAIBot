from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


# Главное меню
def main_menu(is_admin: bool = False):
    buttons = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="ℹ️ О боте")]
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# Клавиатура отмены
def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


# Админ меню
def admin_menu():
    buttons = [
        [KeyboardButton(text="📂 Управление категориями")],
        [KeyboardButton(text="📘 Управление курсами")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# Инлайн-кнопки категорий
def categories_inline(categories):
    buttons = [
        [InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}")]
        for c in categories
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Инлайн-кнопки курсов (покупка)
def courses_inline(courses):
    buttons = [
        [InlineKeyboardButton(
            text=f"💳 Купить ({int(course['price'])} ₽)",
            callback_data=f"buy:{course['id']}"
        )]
        for course in courses
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Инлайн для редактирования/удаления
def edit_delete_inline(entity: str, items):
    buttons = []
    for it in items:
        title = it.get("title") or it.get("name") or ""
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {title}", callback_data=f"edit_{entity}:{it['id']}"),
            InlineKeyboardButton(text=f"🗑 {title}", callback_data=f"delete_{entity}:{it['id']}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)








