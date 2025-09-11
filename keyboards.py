from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


# --- Главное меню ---
def main_menu(is_admin: bool = False):
    buttons = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="ℹ️ О боте")]
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# --- Админ меню ---
def admin_menu():
    buttons = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="➕ Добавить категорию")],
        [KeyboardButton(text="➕ Добавить курс")],
        [KeyboardButton(text="ℹ️ О боте")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# --- Кнопка отмены ---
def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


# --- Список категорий ---
def categories_keyboard(categories, admin: bool = False):
    buttons = []
    for c in categories:
        buttons.append([InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}")])
    if admin:
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- Курс ---
def course_keyboard(course_id: int, price: int, title: str):
    buttons = [
        [InlineKeyboardButton(text=f"💳 Купить ({price}₽)", callback_data=f"buy:{course_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)








