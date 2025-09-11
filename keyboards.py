from aiogram import types


def main_menu(admin: bool = False):
    buttons = [
        [types.KeyboardButton(text="📚 Курсы")],
        [types.KeyboardButton(text="ℹ️ О боте")]
    ]
    if admin:
        buttons.append([types.KeyboardButton(text="👑 Админ-панель")])
    return types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def categories_inline(categories):
    buttons = [
        [types.InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}")]
        for c in categories
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def course_inline(course):
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text=f"💳 Оплатить — {course['price']} ₽",
                callback_data=f"buy:{course['id']}"
            )]
        ]
    )


# --- ADMIN ---
admin_menu = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="Управление курсами")],
        [types.KeyboardButton(text="Управление категориями")],
        [types.KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)


def categories_admin_inline(categories):
    buttons = [
        [types.InlineKeyboardButton(text=f"❌ {c['title']}", callback_data=f"delcat:{c['id']}")]
        for c in categories
    ]
    buttons.append([types.InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_courses_inline(courses):
    buttons = [
        [types.InlineKeyboardButton(text=f"❌ {c['title']}", callback_data=f"delcourse:{c['id']}")]
        for c in courses
    ]
    buttons.append([types.InlineKeyboardButton(text="➕ Добавить курс", callback_data="admin_add_course")])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


# Cancel keyboard
cancel_kb = types.ReplyKeyboardMarkup(
    keyboard=[[types.KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)





