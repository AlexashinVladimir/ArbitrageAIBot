"""
Bot.py — полный рабочий бот (Aiogram 3.6).
Содержит: меню, админ-панель, CRUD категорий/курсов, платежи.
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
import aiosqlite

import db
import keyboards as kb
import texts
from states import AddCategory, AddCourse, EditCourse

# env
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENTS_PROVIDER_TOKEN = os.getenv("PAYMENTS_PROVIDER_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", db.DB_PATH)
CURRENCY = os.getenv("CURRENCY", "RUB")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set in .env")
if not PAYMENTS_PROVIDER_TOKEN:
    raise RuntimeError("PAYMENTS_PROVIDER_TOKEN not set in .env")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Startup: ensure DB
async def on_startup():
    await db.init_db(DB_PATH)
    # ensure admin user present (optional)
    if ADMIN_ID:
        await db.ensure_user(ADMIN_ID, is_admin=True)
    print("Startup ok. DB initialized.")

# ----------------- Handlers -----------------

@dp.message(Command('start'))
async def cmd_start(message: Message):
    is_admin = message.from_user.id == ADMIN_ID
    await db.ensure_user(message.from_user.id)
    await message.answer(texts.random_start(), reply_markup=kb.main_menu(admin=is_admin))

@dp.message(F.text == "ℹ️ О боте")
async def about(message: Message):
    await message.answer(texts.random_about())

# User: show categories
@dp.message(F.text == "📚 Курсы")
async def list_categories(message: Message):
    cats = await db.list_categories()
    if not cats:
        await message.answer(texts.CATEGORY_EMPTY)
        return
    await message.answer("Выбери категорию:", reply_markup=kb.categories_inline(cats))

@dp.callback_query(F.data.startswith("category:"))
async def category_cb(callback: types.CallbackQuery):
    cat_id = int(callback.data.split(":", 1)[1])
    courses = await db.list_courses_by_category(cat_id)
    if not courses:
        await callback.message.answer(texts.COURSE_EMPTY)
        await callback.answer()
        return
    for c in courses:
        text = f"<b>{c['title']}</b>\n\n{c['description']}\n\nЦена: {c['price']} {CURRENCY}"
        await callback.message.answer(text, reply_markup=kb.course_inline(c['id']))
    await callback.answer()

# Buy
@dp.callback_query(F.data.startswith("buy:"))
async def buy_cb(callback: types.CallbackQuery):
    course_id = int(callback.data.split(":", 1)[1])
    course = await db.get_course(course_id)
    if not course:
        await callback.answer("Курс не найден.", show_alert=True)
        return
    amount = int(course['price'])  # stored as integer representing rubles
    labeled_price = [LabeledPrice(label=course['title'], amount=amount * 100)]
    payload = f"course:{course_id}"
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course['title'],
        description=course['description'] or "",
        payload=payload,
        provider_token=PAYMENTS_PROVIDER_TOKEN,
        currency=CURRENCY,
        prices=labeled_price,
        start_parameter=f"buy_{course_id}"
    )
    await callback.answer()

@dp.pre_checkout_query()
async def precheckout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    pay = message.successful_payment
    payload = pay.invoice_payload
    if payload and payload.startswith("course:"):
        course_id = int(payload.split(":", 1)[1])
        await db.record_purchase(message.from_user.id, course_id)
        course = await db.get_course(course_id)
        if course and course.get('link'):
            await message.answer(texts.random_payment_success(course['title']) + f"\n\nСсылка: {course['link']}")
        else:
            await message.answer("Оплата прошла, но ссылка не найдена. Свяжитесь с админом.")
    else:
        await message.answer("Оплата принята, но не удалось сопоставить курс.")

# Admin menu button
@dp.message(F.text == "👑 Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY)
        return
    await message.answer("Панель администратора:", reply_markup=kb.admin_menu)

# Manage categories
@dp.message(F.text == "Управление категориями")
async def manage_categories(message: Message):
    cats = await db.list_categories()
    await message.answer("Категории:", reply_markup=kb.categories_admin_inline(cats))

@dp.callback_query(F.data == "admin_add_category")
async def admin_add_category_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название новой категории:", reply_markup=kb.cancel_kb)
    await state.set_state(AddCategory.waiting_for_title)
    await callback.answer()

@dp.message(StateFilter(AddCategory.waiting_for_title))
async def admin_add_category_finish(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCELLED, reply_markup=kb.admin_menu)
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена.", reply_markup=kb.admin_menu)

@dp.callback_query(F.data.startswith("delcat:"))
async def delcat_cb(callback: types.CallbackQuery):
    cat_id = int(callback.data.split(":",1)[1])
    await db.delete_category(cat_id)
    await callback.message.answer("Категория удалена.", reply_markup=kb.admin_menu)
    await callback.answer()

# Manage courses
@dp.message(F.text == "Управление курсами")
async def manage_courses(message: Message):
    courses = await db.list_courses()
    await message.answer("Курсы:", reply_markup=kb.admin_courses_inline(courses))

@dp.callback_query(F.data == "admin_add_course")
async def admin_add_course_start(callback: types.CallbackQuery, state: FSMContext):
    cats = await db.list_categories()
    if not cats:
        await callback.message.answer("Сначала добавьте категорию.")
        await callback.answer()
        return
    # reply keyboard with category titles
    buttons = [[types.KeyboardButton(text=c['title'])] for c in cats]
    kb_reply = types.ReplyKeyboardMarkup(
        keyboard=buttons + [[types.KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )
    await callback.message.answer("Выберите категорию для курса:", reply_markup=kb_reply)
    await state.set_state(AddCourse.waiting_for_category)
    await state.update_data(categories=[dict(c) for c in cats])
    await callback.answer()

@dp.message(StateFilter(AddCourse.waiting_for_category))
async def admin_add_course_category(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu)
        return
    data = await state.get_data()
    cats = data.get("categories", [])
    selected = next((c for c in cats if c['title'] == message.text), None)
    if not selected:
        await message.answer("Выбери категорию из клавиатуры.")
        return
    await state.update_data(category_id=selected['id'])
    await state.set_state(AddCourse.waiting_for_title)
    await message.answer("Введи название курса:", reply_markup=kb.cancel_kb)

@dp.message(StateFilter(AddCourse.waiting_for_title))
async def admin_add_course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu)
        return
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Введи описание курса:", reply_markup=kb.cancel_kb)

@dp.message(StateFilter(AddCourse.waiting_for_description))
async def admin_add_course_desc(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu)
        return
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Введи цену (только число, в рублях):", reply_markup=kb.cancel_kb)

@dp.message(StateFilter(AddCourse.waiting_for_price))
async def admin_add_course_price(message: Message, state: FSMContext):
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
async def admin_add_course_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu)
        return
    data = await state.get_data()
    await db.add_course(
        category_id=data["category_id"],
        title=data["title"],
        description=data["description"],
        price=data["price"],
        link=message.text
    )
    await state.clear()
    await message.answer("Курс добавлен.", reply_markup=kb.admin_menu)

# Admin course actions: view / edit / delete
@dp.callback_query(F.data.startswith("admin_course:"))
async def admin_course_cb(callback: types.CallbackQuery):
    course_id = int(callback.data.split(":",1)[1])
    course = await db.get_course(course_id)
    if not course:
        await callback.answer("Курс не найден.", show_alert=True)
        return
    text = f"<b>{course['title']}</b>\n\n{course['description']}\n\nЦена: {course['price']} {CURRENCY}\nСсылка: {course['link'] or '-'}"
    await callback.message.answer(text, reply_markup=kb.course_admin_inline(course_id))
    await callback.answer()

@dp.callback_query(F.data.startswith("delcourse:"))
async def delcourse_cb(callback: types.CallbackQuery):
    course_id = int(callback.data.split(":",1)[1])
    await db.delete_course(course_id)
    await callback.message.answer("Курс удалён.", reply_markup=kb.admin_menu)
    await callback.answer()

@dp.callback_query(F.data.startswith("editcourse:"))
async def editcourse_start(callback: types.CallbackQuery, state: FSMContext):
    course_id = int(callback.data.split(":",1)[1])
    await state.update_data(course_id=course_id)
    await state.set_state(EditCourse.waiting_for_field)
    await callback.message.answer("Что редактируем?", reply_markup=kb.edit_course_kb)
    await callback.answer()

@dp.message(StateFilter(EditCourse.waiting_for_field))
async def editcourse_field(message: Message, state: FSMContext):
    field_map = {"Название":"title","Описание":"description","Цена":"price","Ссылка":"link"}
    if message.text not in field_map:
        await message.answer("Выбери из кнопок.")
        return
    await state.update_data(field=field_map[message.text])
    await state.set_state(EditCourse.waiting_for_value)
    await message.answer(f"Введи новое значение для {message.text}:", reply_markup=kb.cancel_kb)

@dp.message(StateFilter(EditCourse.waiting_for_value))
async def editcourse_value(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu)
        return
    data = await state.get_data()
    field = data['field']
    val = message.text
    if field == "price":
        if not val.isdigit():
            await message.answer("Цена должна быть числом.")
            return
        val = int(val)
    await db.update_course_field(data['course_id'], field, val)
    await state.clear()
    await message.answer("Курс обновлён.", reply_markup=kb.admin_menu)

# fallback
@dp.message()
async def fallback(message: Message):
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(texts.random_fallback(), reply_markup=kb.main_menu(admin=is_admin))

# Run
async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())






