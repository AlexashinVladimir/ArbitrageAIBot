from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


# Главное меню
def main_menu(is_admin=False):
    buttons = [
        [KeyboardButton(text="📚 Категории")],
        [KeyboardButton(text="ℹ️ О боте")]
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# Админ-панель
def admin_panel():
    buttons = [
        [KeyboardButton(text="➕ Добавить категорию")],
        [KeyboardButton(text="➕ Добавить курс")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# Кнопка отмены
def cancel():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]], resize_keyboard=True
    )


# Список категорий
def categories_inline(categories):
    markup = InlineKeyboardMarkup()
    for c in categories:
        markup.add(InlineKeyboardButton(text=c["title"], callback_data=f"cat_{c['id']}"))
    return markup


# Список курсов
def courses_inline(courses):
    markup = InlineKeyboardMarkup()
    for course in courses:
        markup.add(InlineKeyboardButton(text=course["title"], callback_data=f"course_{course['id']}"))
    return markup


# Купить курс
def buy_course(course_id, price, title):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            text=f"💳 Купить за {price}₽",
            callback_data=f"buy_{course_id}_{price}_{title}"
        )
    )
    return markup








