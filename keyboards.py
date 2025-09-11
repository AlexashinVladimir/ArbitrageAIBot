# keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Reply keyboards
def main_menu(admin: bool = False):
    buttons = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="ℹ️ О боте")]
    ]
    if admin:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_menu():
    buttons = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="➕ Добавить категорию")],
        [KeyboardButton(text="📂 Управление категориями")],
        [KeyboardButton(text="➕ Добавить курс")],
        [KeyboardButton(text="📘 Управление курсами")],
        [KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

# Inline: categories
def categories_inline(categories):
    kb = InlineKeyboardMarkup()
    for c in categories:
        kb.add(InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}"))
    return kb

# Inline: courses list with buy button per course (shows price on button)
def courses_inline(courses):
    kb = InlineKeyboardMarkup()
    for course in courses:
        price = int(course.get("price", 0) or 0)
        kb.add(InlineKeyboardButton(text=f"💳 Купить ({price} ₽)", callback_data=f"buy:{course['id']}"))
    return kb

# Inline edit/delete for entities. entity is 'category' or 'course'
def edit_delete_inline(entity: str, items):
    kb = InlineKeyboardMarkup()
    for it in items:
        title = it.get("title") or it.get("name") or ""
        kb.row(
            InlineKeyboardButton(text=f"✏️ {title}", callback_data=f"edit_{entity}:{it['id']}"),
            InlineKeyboardButton(text=f"🗑 {title}", callback_data=f"delete_{entity}:{it['id']}")
        )
    return kb









