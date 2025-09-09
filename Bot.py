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
    await callback.m





