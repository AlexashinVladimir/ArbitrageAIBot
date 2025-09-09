import os
from dotenv import load_dotenv
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import LabeledPrice, PreCheckoutQuery

import db
import keyboards as kb
import texts
import states

# --- Load env ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- Start ---
@dp.message(Command("start"))
async def start(message: Message):
    await db.init_db()
    await message.answer(texts.START_TEXT, reply_markup=kb.main_menu_kb())

# --- Admin panel ---
@dp.message(F.text == "🛠️ Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа")
        return
    kb_admin = ReplyKeyboardMarkup(resize_keyboard=True)
    kb_admin.add(KeyboardButton("➕ Добавить категорию"))
    kb_admin.add(KeyboardButton("➕ Добавить курс"))
    kb_admin.add(KeyboardButton("❌ Отмена"))
    await message.answer(texts.ADMIN_PANEL_TEXT, reply_markup=kb_admin)

# --- Add Category ---
@dp.message(F.text == "➕ Добавить категорию")
async def add_category_start(message: Message, state: FSMContext):
    await state.set_state(states.AddCategory.waiting_name)
    await message.answer(texts.ADD_CATEGORY_PROMPT, reply_markup=kb.cancel_kb())

@dp.message(states.AddCategory.waiting_name)
async def add_category_process(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCEL_TEXT, reply_markup=kb.main_menu_kb())
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена!", reply_markup=kb.main_menu_kb())

# --- List Categories ---
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категории отсутствуют")
        return
    await message.answer(texts.CATEGORY_PROMPT, reply_markup=kb.category_kb(categories))

# --- List Courses by category ---
@dp.callback_query(F.data.startswith("user_cat:"))
async def show_courses(query: CallbackQuery):
    category_id = int(query.data.split(":")[1])
    courses = await db.get_courses(category_id)
    if not courses:
        await query.message.answer("Курсы в этой категории отсутствуют")
        return
    for course in courses:
        text = f"{course[2]}\nЦена: {course[4]}₽\nОписание: {course[3]}"
        await query.message.answer(text, reply_markup=kb.pay_kb(course[0]))

# --- Payments (заглушка) ---
@dp.callback_query(F.data.startswith("pay:"))
async def pay_course(query: CallbackQuery):
    course_id = int(query.data.split(":")[1])
    await query.message.answer("Здесь будет кнопка оплаты, когда будет токен провайдера.")

# --- Run ---
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(dp.start_polling(bot))



