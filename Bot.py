import asyncio
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from dotenv import load_dotenv

import aiosqlite

import db
import keyboards as kb
from states import AddCategory, AddCourse, EditCourse

# Загружаем переменные окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PAYMENTS_PROVIDER_TOKEN = os.getenv("PAYMENTS_PROVIDER_TOKEN")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env")
if not PAYMENTS_PROVIDER_TOKEN:
    raise ValueError("❌ PAYMENTS_PROVIDER_TOKEN не найден в .env")

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ===========================
# 🔹 Общие хендлеры
# ===========================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "👋 Добро пожаловать! Здесь ты можешь выбрать курс или познать истину через мои слова.",
        reply_markup=kb.main_menu(admin)
    )


@dp.message(F.text == "ℹ️ О боте")
async def about_handler(message: Message):
    await message.answer(
        "Я циничный ИИ. Моя задача — продать тебе знание, которое изменит твою жизнь. "
        "Если не изменит — это уже твоя вина."
    )


# ===========================
# 🔹 Пользователь: курсы
# ===========================

@dp.message(F.text == "📚 Курсы")
async def list_categories(message: Message):
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM categories")
        categories = await cur.fetchall()

    if not categories:
        await message.answer("Категорий пока нет.")
        return

    await message.answer("Выбери категорию:", reply_markup=kb.categories_inline([dict(c) for c in categories]))


@dp.callback_query(F.data.startswith("category:"))
async def list_courses(callback: types.CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM courses WHERE category_id=?", (cat_id,))
        courses = await cur.fetchall()

    if not courses:
        await callback.message.answer("В этой категории пока нет курсов.")
        await callback.answer()
        return

    for c in courses:
        text = f"<b>{c['title']}</b>\n\n{c['description']}\n\nЦена: {c['price']} руб."
        await callback.message.answer(text, reply_markup=kb.course_inline(c["id"]))

    await callback.answer()


@dp.callback_query(F.data.startswith("buy:"))
async def buy_course(callback: types.CallbackQuery):
    course_id = int(callback.data.split(":")[1])

    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM courses WHERE id=?", (course_id,))
        course = await cur.fetchone()

    if not course:
        await callback.answer("Курс не найден", show_alert=True)
        return

    prices = [LabeledPrice(label=course["title"], amount=course["price"] * 100)]

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course["title"],
        description=course["description"],
        payload=str(course_id),
        provider_token=PAYMENTS_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices
    )
    await callback.answer()


@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    course_id = int(message.successful_payment.invoice_payload)
    user_id = message.from_user.id

    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO purchases (user_id, course_id) VALUES (?, ?)",
            (user_id, course_id)
        )
        await conn.commit()

        cur = await conn.execute("SELECT link FROM courses WHERE id=?", (course_id,))
        row = await cur.fetchone()

    if row and row["link"]:
        await message.answer(f"✅ Оплата прошла успешно!\nВот твоя ссылка: {row['link']}")
    else:
        await message.answer("✅ Оплата прошла, но ссылка к курсу не найдена. Обратись к админу.")


# ===========================
# 🔹 Админ-панель
# ===========================

@dp.message(F.text == "👑 Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Ты не админ.")
        return
    await message.answer("Добро пожаловать в админку.", reply_markup=kb.admin_menu)


# --- Категории ---

@dp.message(F.text == "Управление категориями")
async def manage_categories(message: Message):
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM categories")
        categories = await cur.fetchall()

    await message.answer(
        "Категории:",
        reply_markup=kb.categories_admin_inline([dict(c) for c in categories])
    )


@dp.callback_query(F.data == "admin_add_category")
async def add_category_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введи название новой категории:", reply_markup=kb.cancel_kb)
    await state.set_state(AddCategory.waiting_for_title)
    await callback.answer()


@dp.message(StateFilter(AddCategory.waiting_for_title))
async def add_category_finish(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.main_menu(message.from_user.id == ADMIN_ID))
        return

    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute("INSERT INTO categories (title) VALUES (?)", (message.text,))
        await conn.commit()

    await message.answer("✅ Категория добавлена.", reply_markup=kb.admin_menu)
    await state.clear()


@dp.callback_query(F.data.startswith("delcat:"))
async def delete_category(callback: types.CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        await conn.commit()

    await callback.message.answer("❌ Категория удалена.")
    await callback.answer()


# --- Курсы ---

@dp.message(F.text == "Управление курсами")
async def manage_courses(message: Message):
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM courses")
        courses = await cur.fetchall()

    if not courses:
        await message.answer("Курсов пока нет.", reply_markup=kb.admin_menu)
        return

    await message.answer(
        "Курсы:",
        reply_markup=kb.admin_courses_inline([dict(c) for c in courses])
    )


@dp.callback_query(F.data == "admin_add_course")
async def add_course_start(callback: types.CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM categories")
        categories = await cur.fetchall()

    if not categories:
        await callback.message.answer("Сначала создай категорию.")
        await callback.answer()
        return

    buttons = [[types.KeyboardButton(text=c["title"])] for c in categories]
    kb_select = types.ReplyKeyboardMarkup(
        keyboard=buttons + [[types.KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

    await callback.message.answer("Выбери категорию:", reply_markup=kb_select)
    await state.set_state(AddCourse.waiting_for_category)
    await callback.answer()


@dp.message(StateFilter(AddCourse.waiting_for_category))
async def add_course_category(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu)
        return

    async with aiosqlite.connect(db.DB_PATH) as conn:
        cur = await conn.execute("SELECT id FROM categories WHERE title=?", (message.text,))
        row = await cur.fetchone()

    if not row:
        await message.answer("Такой категории нет. Попробуй снова.")
        return

    await state.update_data(category_id=row[0])
    await state.set_state(AddCourse.waiting_for_title)
    await message.answer("Введи название курса:", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(AddCourse.waiting_for_title))
async def add_course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu)
        return

    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Введи описание курса:", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(AddCourse.waiting_for_description))
async def add_course_desc(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu)
        return

    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Введи цену курса (только число):", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(AddCourse.waiting_for_price))
async def add_course_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu)
        return

    if not message.text.isdigit():
        await message.answer("Цена должна быть числом.")
        return

    await state.update_data(price=int(message.text))
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Введи ссылку на курс:", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(AddCourse.waiting_for_link))
async def add_course_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu)
        return

    data = await state.get_data()
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO courses (category_id, title, description, price, link) VALUES (?, ?, ?, ?, ?)",
            (data["category_id"], data["title"], data["description"], data["price"], message.text)
        )
        await conn.commit()

    await state.clear()
    await message.answer("✅ Курс добавлен!", reply_markup=kb.admin_menu)


# ===========================
# 🔹 Запуск бота
# ===========================

async def main():
    await db.init_db()
    print("Бот запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())





