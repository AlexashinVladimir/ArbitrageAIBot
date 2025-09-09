"""
Bot.py — основной файл бота.
Поддержка: Aiogram 3.6+, SQLite (через aiosqlite), Polling, Telegram Payments.
Функционал: просмотр курсов, покупка, админка (категории и курсы).
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
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
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

    # проверка: если админ → показать меню с кнопкой "⚙️ Админ"
    if message.from_user.id == ADMIN_ID:
        menu = kb.main_menu(admin=True)
    else:
        menu = kb.main_menu()

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
    text = f"<b>{course['title']}</b>\n{course['description'] or ''}\nЦена: {course['price'] / 100:.2f} {course['currency']}"
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
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM courses")
            rows = await cur.fetchall()
            for r in rows:
                if int(r["price"]) == int(pay.total_amount) and r["currency"] == pay.currency:
                    course = dict(r)
                    break

    if not course:
        await message.answer("Платёж получен, но курс не найден.")
        return

    user_db_id = await db.ensure_user(message.from_user.id)
    await db.record_purchase(user_db_id, course["id"], datetime.utcnow().isoformat(), payload)

    await message.answer(texts.COURSE_PURCHASED.format(title=course["title"]))
    await message.answer(f"Материалы курса:\n{course['description'] or 'Описание отсутствует.'}")


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




