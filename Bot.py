"""
Bot.py — основной файл бота.
Поддержка: Aiogram 3.6+, SQLite (через aiosqlite), Polling, Telegram Payments.
"""

import asyncio
import logging
import os
import secrets
from datetime import datetime

from dotenv import load_dotenv
import aiosqlite

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import LabeledPrice, PreCheckoutQuery, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# Модули проекта
import db
import keyboards as kb
import texts
from states import AddCategory, AddCourse, EditCourse

# -------------------- Загрузка окружения --------------------
load_dotenv()
TOKEN = os.getenv('TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
PAYMENT_PROVIDER_TOKEN = os.getenv('PAYMENT_PROVIDER_TOKEN')
CURRENCY = os.getenv('CURRENCY', 'RUB')
DB_PATH = os.getenv('DB_PATH', 'data.db')

if not TOKEN:
    raise RuntimeError("TOKEN is not set in .env")

# -------------------- Логирование --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------- Бот и диспетчер --------------------
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# -------------------- Startup --------------------
async def on_startup():
    await db.init_db(DB_PATH)
    if ADMIN_ID:
        await db.ensure_user(ADMIN_ID, is_admin=True)
    logger.info("Startup completed.")


# -------------------- Пользовательские команды --------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await db.ensure_user(message.from_user.id)
    menu = kb.main_menu(admin=(message.from_user.id == ADMIN_ID))
    await message.answer(texts.START, reply_markup=menu)


@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY)
        return
    await message.answer("Админ-панель:", reply_markup=kb.admin_menu())


@dp.message(F.text == "ℹ️ О боте")
async def about_handler(message: types.Message):
    await message.answer(texts.ABOUT)


@dp.message(F.text == "📚 Курсы")
async def show_categories(message: types.Message):
    categories = await db.list_categories(active_only=True)
    if not categories:
        await message.answer(texts.CATEGORY_EMPTY)
        return
    await message.answer("Выберите категорию:", reply_markup=kb.categories_inline(categories))


@dp.message(F.text == "⚙️ Админ")
async def open_admin_menu(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY)
        return
    await message.answer("Админ-панель:", reply_markup=kb.admin_menu())


@dp.callback_query(lambda c: c.data and c.data.startswith("category:"))
async def category_callback(callback: types.CallbackQuery):
    await callback.answer()
    cat_id = int(callback.data.split(":", 1)[1])
    courses = await db.list_courses_by_category(cat_id)
    if not courses:
        await callback.message.answer(texts.COURSE_EMPTY)
        return
    await callback.message.answer("Курсы в категории:", reply_markup=kb.courses_inline(courses))


@dp.callback_query(lambda c: c.data and c.data.startswith("course_show:"))
async def course_show_cb(cb: types.CallbackQuery):
    await cb.answer()
    course_id = int(cb.data.split(":", 1)[1])
    course = await db.get_course(course_id)
    if not course:
        await cb.message.answer("Курс не найден.")
        return
    text = (
        f"<b>{course['title']}</b>\n"
        f"{course['description'] or ''}\n"
        f"Цена: {course['price'] / 100:.2f} {course['currency']}"
    )
    await cb.message.answer(text, reply_markup=kb.course_detail_inline(course))


# -------------------- Оплата --------------------
@dp.callback_query(lambda c: c.data and c.data.startswith("course_pay:"))
async def course_pay_cb(cb: types.CallbackQuery):
    await cb.answer()
    payload = cb.data.split(":", 1)[1]
    course = await db.get_course_by_payload(payload)
    if not course:
        await cb.message.answer("Курс не найден.")
        return

    title = course["title"]
    description = course["description"] or title
    price_value = int(course["price"])
    labeled_price = [LabeledPrice(label=title, amount=price_value)]
    invoice_payload = f"course_{course['id']}_{secrets.token_hex(6)}"

    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title=title,
        description=description,
        payload=invoice_payload,
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency=course["currency"],
        prices=labeled_price,
        start_parameter=f"buy_{course['id']}",
    )


@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    pay = message.successful_payment
    payload = pay.invoice_payload
    course = None

    if payload and payload.startswith("course_"):
        try:
            course_id = int(payload.split("_")[1])
            course = await db.get_course(course_id)
        except Exception:
            course = None

    if not course:
        await message.answer("Платёж получен, но курс не найден.")
        return

    user_db_id = await db.ensure_user(message.from_user.id)
    await db.record_purchase(user_db_id, course["id"], datetime.utcnow().isoformat(), payload)

    await message.answer(texts.COURSE_PURCHASED.format(title=course["title"]))
    await message.answer(f"Ссылка на материалы курса: {course['link']}")


# -------------------- Admin: Курсы --------------------
@dp.message(F.text == "Управление курсами")
async def admin_manage_courses(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY)
        return
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM courses ORDER BY id")
        rows = await cur.fetchall()
        courses = [dict(r) for r in rows]
    if not courses:
        await message.answer("Курсов пока нет.")
        return
    await message.answer("Список курсов:", reply_markup=kb.admin_courses_inline(courses))


# -------------------- Admin: Категории --------------------
@dp.message(F.text == "Управление категориями")
async def admin_manage_categories(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY)
        return
    categories = await db.list_categories(active_only=False)
    await message.answer("Управление категориями:", reply_markup=kb.admin_categories_inline(categories))


# -------------------- Admin: Добавление категорий --------------------
@dp.callback_query(F.data == "admin_add_category")
async def admin_add_category_cb(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(AddCategory.waiting_for_title)
    await cb.message.answer("Введите название новой категории:")


@dp.message(AddCategory.waiting_for_title)
async def process_new_category(message: types.Message, state: FSMContext):
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена.", reply_markup=kb.main_menu(admin=(message.from_user.id == ADMIN_ID)))


# -------------------- Admin: Добавление курса --------------------
@dp.callback_query(F.data == "admin_add_course")
async def admin_add_course_cb(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    categories = await db.list_categories(active_only=True)
    if not categories:
        await cb.message.answer("Сначала создайте категорию.")
        return
    buttons = [[types.KeyboardButton(c["title"])] for c in categories]
    await state.set_state(AddCourse.waiting_for_category)
    await state.update_data(categories=categories)
    await cb.message.answer(
        "Выберите категорию:",
        reply_markup=types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    )


@dp.message(AddCourse.waiting_for_category)
async def add_course_category(message: types.Message, state: FSMContext):
    data = await state.get_data()
    categories = data.get("categories", [])
    cat = next((c for c in categories if c["title"] == message.text), None)
    if not cat:
        await message.answer("Выберите категорию из списка.")
        return
    await state.update_data(category_id=cat["id"])
    await state.set_state(AddCourse.waiting_for_title)
    await message.answer("Введите название курса:", reply_markup=types.ReplyKeyboardRemove())


@dp.message(AddCourse.waiting_for_title)
async def add_course_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Введите описание курса:")


@dp.message(AddCourse.waiting_for_description)
async def add_course_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Введите цену курса (в рублях):")


@dp.message(AddCourse.waiting_for_price)
async def add_course_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число.")
        return
    await state.update_data(price=int(message.text) * 100)
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Введите ссылку на материалы курса:")


@dp.message(AddCourse.waiting_for_link)
async def add_course_link(message: types.Message, state: FSMContext):
    data = await state.get_data()
    payload = secrets.token_hex(8)
    await db.add_course(
        category_id=data["category_id"],
        title=data["title"],
        description=data["description"],
        price=data["price"],
        currency=CURRENCY,
        link=message.text,
        payload=payload
    )
    await state.clear()
    await message.answer("Курс добавлен ✅", reply_markup=kb.main_menu(admin=(message.from_user.id == ADMIN_ID)))


# -------------------- Admin: Редактирование курса --------------------
@dp.callback_query(F.data.startswith("admin_course:"))
async def admin_edit_course(cb: types.CallbackQuery):
    await cb.answer()
    course_id = int(cb.data.split(":")[1])
    course = await db.get_course(course_id)
    if not course:
        await cb.message.answer("Курс не найден.")
        return
    await cb.message.answer(f"Редактирование курса: {course['title']}", reply_markup=kb.edit_course_inline(course_id))


@dp.callback_query(F.data.startswith("edit_course_"))
async def edit_course_field(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    parts = cb.data.split(":")
    field, course_id = parts[0].replace("edit_course_", ""), int(parts[1])
    await state.set_state(EditCourse.waiting_for_value)
    await state.update_data(field=field, course_id=course_id)
    await cb.message.answer(f"Введите новое значение для поля {field}:")


@dp.message(EditCourse.waiting_for_value)
async def process_edit_course(message: types.Message, state: FSMContext):
    data = await state.get_data()
    field = data["field"]
    course_id = data["course_id"]
    value = message.text

    column = {
        "title": "title",
        "description": "description",
        "price": "price",
        "link": "link"
    }.get(field)

    if column == "price":
        if not value.isdigit():
            await message.answer("Цена должна быть числом.")
            return
        value = int(value) * 100

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(f"UPDATE courses SET {column}=? WHERE id=?", (value, course_id))
        await conn.commit()

    await state.clear()
    await message.answer("Курс обновлён ✅", reply_markup=kb.main_menu(admin=(message.from_user.id == ADMIN_ID)))


# -------------------- Admin: Удаление курса --------------------
@dp.callback_query(F.data.startswith("delete_course:"))
async def delete_course_cb(cb: types.CallbackQuery):
    await cb.answer()
    course_id = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM courses WHERE id=?", (course_id,))
        await conn.commit()
    await cb.message.answer("Курс удалён ❌", reply_markup=kb.main_menu(admin=(cb.from_user.id == ADMIN_ID)))


# -------------------- Отмена --------------------
@dp.message(F.text == "❌ Отмена")
async def cancel_by_text(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=kb.main_menu(admin=(message.from_user.id == ADMIN_ID)))


@dp.message()
async def fallback(message: types.Message):
    await message.answer("Неизвестная команда. Используйте главное меню.", reply_markup=kb.main_menu(admin=(message.from_user.id == ADMIN_ID)))


# -------------------- Запуск --------------------
async def main():
    await on_startup()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())



