"""
Bot.py — основной файл с логикой Telegram-бота (адаптирован под Aiogram 3.6).
"""

import asyncio
import os
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode, ContentType
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, LabeledPrice
from aiogram.filters import Command
from dotenv import load_dotenv

import db
import keyboards as kb
import texts
from states import AddCategory, AddCourse, EditCourse

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PAYMENTS_PROVIDER_TOKEN = os.getenv("PAYMENTS_PROVIDER_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# ✅ Aiogram 3.6: используем parse_mode прямо в Bot
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

DB_PATH = db.DB_PATH


# ---------------- START ----------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    admin = (message.from_user.id == ADMIN_ID)
    menu = kb.main_menu(admin=admin)
    await message.answer(texts.random_start(), reply_markup=menu)


# ---------------- О боте ----------------
@dp.message(F.text == "ℹ️ О боте")
async def cmd_about(message: Message):
    await message.answer(texts.random_about())


# ---------------- Курсы ----------------
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM categories ORDER BY id")
        rows = await cur.fetchall()
        categories = [dict(r) for r in rows]

    if not categories:
        await message.answer(texts.CATEGORY_EMPTY)
        return

    await message.answer("Выбери категорию:", reply_markup=kb.categories_inline(categories))


@dp.callback_query(F.data.startswith("category:"))
async def show_courses(callback: types.CallbackQuery):
    category_id = int(callback.data.split(":")[1])

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM courses WHERE category_id = ?", (category_id,))
        rows = await cur.fetchall()
        courses = [dict(r) for r in rows]

    if not courses:
        await callback.message.answer(texts.COURSE_EMPTY)
        await callback.answer()
        return

    for course in courses:
        text = f"<b>{course['title']}</b>\n\n{course['description']}\n\nЦена: {course['price']} ₽"
        await callback.message.answer(
            text,
            reply_markup=kb.course_inline(course_id=course["id"])
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("buy:"))
async def buy_course(callback: types.CallbackQuery):
    course_id = int(callback.data.split(":")[1])

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        course = await cur.fetchone()

    if not course:
        await callback.answer("Курс не найден.", show_alert=True)
        return

    prices = [LabeledPrice(label=course["title"], amount=course["price"] * 100)]

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course["title"],
        description=course["description"],
        provider_token=PAYMENTS_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        payload=f"course:{course['id']}"
    )
    await callback.answer()


@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    course_id = int(payload.split(":")[1])

    async with aiosqlite.connect(DB_PATH) as conn:
        # Сохраняем покупку
        await conn.execute(
            "INSERT OR IGNORE INTO purchases (user_id, course_id) VALUES (?, ?)",
            (message.from_user.id, course_id)
        )
        await conn.commit()

        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        course = await cur.fetchone()

    await message.answer(
        texts.COURSE_PURCHASED.format(title=course["title"]) + f"\n\nСсылка: {course['link']}"
    )


# ---------------- Админ-панель ----------------
@dp.message(F.text == "👑 Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY)
        return
    await message.answer("Добро пожаловать в админ-панель:", reply_markup=kb.admin_menu)


# ---------------- Управление категориями ----------------
@dp.message(F.text == "Управление категориями")
async def manage_categories(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY)
        return

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM categories ORDER BY id")
        rows = await cur.fetchall()
        categories = [dict(r) for r in rows]

    if not categories:
        await message.answer("Категорий пока нет.", reply_markup=kb.categories_admin_inline([]))
    else:
        await message.answer("Список категорий:", reply_markup=kb.categories_admin_inline(categories))


@dp.callback_query(F.data == "admin_add_category")
async def admin_add_category(callback: types.CallbackQuery, state):
    await callback.message.answer("Введи название новой категории:", reply_markup=kb.cancel_kb)
    await state.set_state(AddCategory.waiting_for_title)
    await callback.answer()


@dp.message(AddCategory.waiting_for_title, F.text)
async def add_category(message: Message, state):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCELLED, reply_markup=kb.main_menu(admin=(message.from_user.id == ADMIN_ID)))
        return

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("INSERT INTO categories (title) VALUES (?)", (message.text,))
        await conn.commit()

    await state.clear()
    await message.answer(f"✅ Категория «{message.text}» добавлена!", reply_markup=kb.main_menu(admin=True))


@dp.callback_query(F.data.startswith("delcat:"))
async def delete_category(callback: types.CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await conn.commit()
    await callback.message.answer("Категория удалена.", reply_markup=kb.admin_menu)
    await callback.answer()


# ---------------- Управление курсами ----------------
@dp.message(F.text == "Управление курсами")
async def admin_manage_courses(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY)
        return

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM courses ORDER BY id")
        rows = await cur.fetchall()
        courses = [dict(r) for r in rows]

    if not courses:
        await message.answer("Курсов пока нет.", reply_markup=kb.admin_courses_inline([]))
    else:
        await message.answer("Список курсов:", reply_markup=kb.admin_courses_inline(courses))


# ---------------- Редактирование и удаление курсов ----------------
@dp.callback_query(F.data.startswith("admin_course:"))
async def admin_course_actions(callback: types.CallbackQuery):
    course_id = int(callback.data.split(":")[1])

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        course = await cur.fetchone()

    if not course:
        await callback.answer("Курс не найден.", show_alert=True)
        return

    text = f"<b>{course['title']}</b>\n\n{course['description']}\n\nЦена: {course['price']} ₽\nСсылка: {course['link']}"
    await callback.message.answer(
        text,
        reply_markup=kb.course_admin_inline(course_id=course_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("delcourse:"))
async def delete_course(callback: types.CallbackQuery):
    course_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        await conn.commit()
    await callback.message.answer("Курс удалён.", reply_markup=kb.admin_menu)
    await callback.answer()


@dp.callback_query(F.data.startswith("editcourse:"))
async def edit_course_start(callback: types.CallbackQuery, state):
    course_id = int(callback.data.split(":")[1])
    await state.update_data(course_id=course_id)
    await state.set_state(EditCourse.waiting_for_field)
    await callback.message.answer(
        "Что редактируем?",
        reply_markup=kb.edit_course_kb
    )
    await callback.answer()


@dp.message(EditCourse.waiting_for_field, F.text)
async def edit_course_field(message: Message, state):
    field_map = {
        "Название": "title",
        "Описание": "description",
        "Цена": "price",
        "Ссылка": "link"
    }
    if message.text not in field_map:
        await message.answer("Выбери из кнопок.")
        return

    await state.update_data(field=field_map[message.text])
    await state.set_state(EditCourse.waiting_for_value)
    await message.answer(f"Введи новое значение для «{message.text}»:", reply_markup=kb.cancel_kb)


@dp.message(EditCourse.waiting_for_value, F.text)
async def edit_course_value(message: Message, state):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCELLED, reply_markup=kb.main_menu(admin=True))
        return

    data = await state.get_data()
    course_id = data["course_id"]
    field = data["field"]
    value = message.text

    if field == "price" and not value.isdigit():
        await message.answer("Цена должна быть числом.")
        return

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(f"UPDATE courses SET {field} = ? WHERE id = ?", (value, course_id))
        await conn.commit()

    await state.clear()
    await message.answer("✅ Курс обновлён.", reply_markup=kb.main_menu(admin=True))


# ---------------- Fallback ----------------
@dp.message()
async def fallback(message: types.Message):
    await message.answer(
        texts.random_fallback(),
        reply_markup=kb.main_menu(admin=(message.from_user.id == ADMIN_ID))
    )


# ---------------- Main ----------------
async def main():
    await db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())








