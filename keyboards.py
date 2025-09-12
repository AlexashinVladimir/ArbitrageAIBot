# keyboards.py
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# Reply keyboard for main menu (visible to user, admin flag adds admin button)
def reply_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="ℹ️ О боте")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# Simple reply "cancel" keyboard
def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)


# Inline: categories list (for view or add)
def categories_list(categories: list, for_add: bool = False) -> InlineKeyboardMarkup:
    """
    categories: list of {"id","title"}
    for_add: if True, callbacks use 'catadd:{id}', else 'catview:{id}'
    """
    buttons = []
    for c in categories:
        cb = f"catadd:{c['id']}" if for_add else f"catview:{c['id']}"
        buttons.append([InlineKeyboardButton(text=c["title"], callback_data=cb)])
    # Back to main
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Inline: list of courses (titles only)
def courses_list(courses: list, category_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for c in courses:
        buttons.append([InlineKeyboardButton(text=c["title"], callback_data=f"course:{c['id']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_categories")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Inline: course detail (buy + back to category)
def course_detail(course: dict) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"💳 Купить за {int(course.get('price',0))} ₽", callback_data=f"buy:{course['id']}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_category:{int(course.get('category_id') or 0)}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Inline: admin list for editing/deleting categories
def edit_delete_categories(categories: list) -> InlineKeyboardMarkup:
    buttons = []
    for c in categories:
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {c['title']}", callback_data=f"edit_category:{c['id']}"),
            InlineKeyboardButton(text=f"🗑 {c['title']}", callback_data=f"delete_category:{c['id']}")
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Inline: admin list for editing/deleting courses
def edit_delete_courses(courses: list) -> InlineKeyboardMarkup:
    buttons = []
    for c in courses:
        title = c.get("title") or "—"
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {title}", callback_data=f"edit_course:{c['id']}"),
            InlineKeyboardButton(text=f"🗑 {title}", callback_data=f"delete_course:{c['id']}")
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Inline: when editing a course, choose field
def edit_course_fields(course_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Название", callback_data=f"edit_course_field:title:{course_id}")],
        [InlineKeyboardButton(text="Описание", callback_data=f"edit_course_field:description:{course_id}")],
        [InlineKeyboardButton(text="Цена", callback_data=f"edit_course_field:price:{course_id}")],
        [InlineKeyboardButton(text="Ссылка", callback_data=f"edit_course_field:link:{course_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_admin")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Admin panel (reply keyboard)
def reply_admin_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="➕ Добавить категорию"), KeyboardButton(text="📂 Управление категориями")],
        [KeyboardButton(text="➕ Добавить курс"), KeyboardButton(text="📘 Управление курсами")],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)








