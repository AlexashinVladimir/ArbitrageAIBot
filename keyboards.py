from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu(admin: bool = False):
    buttons = [
        [KeyboardButton(text="📚 Курсы")],
    ]
    if admin:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


def categories_keyboard(categories):
    """Кнопки категорий курсов"""
    buttons = [
        [InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}")]
        for c in categories
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def courses_keyboard(courses):
    """Кнопки курсов внутри категории"""
    buttons = [
        [InlineKeyboardButton(text=f"{c['title']} – {c['price']}₽", callback_data=f"course:{c['id']}")]
        for c in courses
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def course_actions(course_id: int):
    """Кнопки покупки"""
    buttons = [
        [InlineKeyboardButton(text="💳 Купить", callback_data=f"buy:{course_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Админ-панель
def admin_panel():
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category")],
        [InlineKeyboardButton(text="➕ Добавить курс", callback_data="admin_add_course")],
        [InlineKeyboardButton(text="📂 Управление курсами", callback_data="admin_manage_courses")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def manage_courses_keyboard(courses):
    """Кнопки редактирования/удаления курсов"""
    buttons = [
        [
            InlineKeyboardButton(text=f"✏️ {c['title']}", callback_data=f"edit_course:{c['id']}"),
            InlineKeyboardButton(text="❌", callback_data=f"delete_course:{c['id']}")
        ]
        for c in courses
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)






