import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from dotenv import load_dotenv

import keyboards as kb
import db

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")

# FSM классы
class AddCategory(StatesGroup):
    name = State()

class AddCourse(StatesGroup):
    category = State()
    title = State()
    description = State()
    price = State()

# Инициализация
bot = Bot(token=BOT_TOKEN, default=ParseMode.HTML)
dp = Dispatcher()

# --- Команда /start ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "👋 Добро пожаловать!\nВыберите действие:",
        reply_markup=kb.main_menu(is_admin)
    )

# --- О боте ---
@dp.message(F.text == "ℹ️ О боте")
async def about(message: Message):
    await message.answer(
        "🤖 Этот бот позволяет покупать обучающие курсы.\n"
        "Администратор может добавлять и редактировать категории и курсы."
    )

# --- Просмотр категорий ---
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("❌ Пока нет категорий.")
        return
    await message.answer("📂 Выберите категорию:", reply_markup=kb.categories_keyboard(categories))

# --- Просмотр курсов ---
@dp.callback_query(F.data.startswith("category:"))
async def show_courses(callback: CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    courses = await db.get_courses_by_category(category_id)
    if not courses:
        await callback.message.edit_text("❌ В этой категории пока нет курсов.")
        return
    for course in courses:
        text = f"<b>{course['title']}</b>\n\n{course['description']}"
        await callback.message.answer(
            text,
            reply_markup=kb.buy_course_keyboard(course["id"], course["price"])
        )
    await callback.answer()

# --- Покупка курса ---
@dp.callback_query(F.data.startswith("buy:"))
async def buy_course(callback: CallbackQuery):
    course_id = int(callback.data.split(":")[1])
    course = await db.get_course(course_id)
    if not course:
        await callback.answer("❌ Курс не найден", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course["title"],
        description=course["description"],
        payload=f"course_{course_id}",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=course["title"], amount=course["price"] * 100)],
        start_parameter="purchase",
    )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    await message.answer("✅ Оплата прошла успешно! Доступ к курсу открыт.")

# ================== АДМИН-ПАНЕЛЬ ==================

@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа.")
        return
    await message.answer("⚙️ Админ-панель:", reply_markup=kb.admin_panel())

# --- Добавление категории ---
@dp.callback_query(F.data == "add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название новой категории:", reply_markup=kb.cancel_keyboard())
    await state.set_state(AddCategory.name)
    await callback.answer()

@dp.message(StateFilter(AddCategory.name))
async def add_category_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("🚫 Добавление отменено.", reply_markup=kb.main_menu(True))
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer(f"✅ Категория <b>{message.text}</b> добавлена!", reply_markup=kb.main_menu(True))

# --- Добавление курса ---
@dp.callback_query(F.data == "add_course")
async def add_course_start(callback: CallbackQuery, state: FSMContext):
    categories = await db.get_categories()
    if not categories:
        await callback.message.answer("❌ Сначала добавьте категорию.", reply_markup=kb.main_menu(True))
        return
    await callback.message.answer("Выберите категорию:", reply_markup=kb.categories_keyboard(categories))
    await state.set_state(AddCourse.category)
    await callback.answer()

@dp.callback_query(StateFilter(AddCourse.category), F.data.startswith("category:"))
async def add_course_choose_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=category_id)
    await callback.message.answer("Введите название курса:", reply_markup=kb.cancel_keyboard())
    await state.set_state(AddCourse.title)
    await callback.answer()

@dp.message(StateFilter(AddCourse.title))
async def add_course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("🚫 Добавление отменено.", reply_markup=kb.main_menu(True))
        return
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.description)
    await message.answer("Введите описание курса:", reply_markup=kb.cancel_keyboard())

@dp.message(StateFilter(AddCourse.description))
async def add_course_description(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("🚫 Добавление отменено.", reply_markup=kb.main_menu(True))
        return
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.price)
    await message.answer("Введите цену курса (в ₽):", reply_markup=kb.cancel_keyboard())

@dp.message(StateFilter(AddCourse.price))
async def add_course_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("🚫 Добавление отменено.", reply_markup=kb.main_menu(True))
        return
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("⚠️ Введите число (цену в рублях).")
        return

    data = await state.get_data()
    await db.add_course(
        data["category_id"], data["title"], data["description"], price
    )
    await state.clear()
    await message.answer(
        f"✅ Курс <b>{data['title']}</b> добавлен в категорию!",
        reply_markup=kb.main_menu(True)
    )

# --- Отмена в любом состоянии ---
@dp.message(F.text == "❌ Отмена")
async def cancel_any(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🚫 Действие отменено.", reply_markup=kb.main_menu(message.from_user.id == ADMIN_ID))

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


