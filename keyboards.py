from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# главное меню
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Курсы по категориям")],
        [KeyboardButton(text="ℹ️ Как работает наставник ИИ")]
    ],
    resize_keyboard=True
)

# админ — простое reply меню (опционально)
admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/list_categories"), KeyboardButton(text="/list_all_courses")],
        [KeyboardButton(text="/add_category"), KeyboardButton(text="/add_course")]
    ],
    resize_keyboard=True
)

def categories_inline(categories: list):
    """
    categories: list of tuples (id, name, is_active)
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for c in categories:
        cid, name, is_active = c
        label = f"📂 {name} {'(активна)' if is_active else '(скрыта)'}"
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=label, callback_data=f"cat:{cid}")])
    return keyboard

def courses_inline(courses: list):
    """
    courses: list of tuples (id, title, description, price, link, is_active)
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for c in courses:
        cid = c[0]
        title = c[1]
        price = c[3]
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"ℹ️ {title} — {price}₽", callback_data=f"details:{cid}")])
    return keyboard

def course_details_keyboard(course_id: int, price: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Оплатить {price}₽", callback_data=f"buy:{course_id}")],
        [InlineKeyboardButton(text="🔙 Назад к категориям", callback_data="back_to_categories")]
    ])
    return kb
