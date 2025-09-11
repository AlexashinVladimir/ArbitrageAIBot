from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# ==== Главное меню ====
def main_menu(is_admin: bool = False):
    buttons = [
        [KeyboardButton(text="📚 Курсы")],
        [KeyboardButton(text="ℹ️ О боте")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


# ==== Админ-панель ====
def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📂 Управление категориями")],
            [KeyboardButton(text="📘 Управление курсами")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True
    )


# ==== Кнопки управления категориями ====
def categories_admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить категорию")],
            [KeyboardButton(text="✏️ Редактировать категорию")],
            [KeyboardButton(text="🗑 Удалить категорию")],
            [KeyboardButton(text="⬅️ Назад")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True
    )


# ==== Кнопки управления курсами ====
def courses_admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить курс")],
            [KeyboardButton(text="✏️ Редактировать курс")],
            [KeyboardButton(text="🗑 Удалить курс")],
            [KeyboardButton(text="⬅️ Назад")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True
    )


# ==== Кнопка отмены ====
def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


# ==== Инлайн-кнопки с категориями ====
def categories_inline(categories: list[dict]):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cat["title"], callback_data=f"category_{cat['id']}")]
            for cat in categories
        ]
    )
    return kb


# ==== Инлайн-кнопки с курсами (цена на кнопке) ====
def courses_inline(courses: list[dict]):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"💳 Купить ({course['price']} ₽)",
                    callback_data=f"buy_{course['id']}"
                )
            ]
            for course in courses
        ]
    )
    return kb


# ==== Инлайн-кнопки для редактирования/удаления ====
def edit_delete_inline(entity: str, items: list[dict]):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✏️ {item['title']}",
                    callback_data=f"edit_{entity}_{item['id']}"
                ),
                InlineKeyboardButton(
                    text=f"🗑 {item['title']}",
                    callback_data=f"delete_{entity}_{item['id']}"
                ),
            ]
            for item in items
        ]
    )
    return kb








