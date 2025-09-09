import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.filters.text import Text
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
import os

import db, keyboards as kb, texts, states

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())

# Инициализация базы
asyncio.run(db.init_db())

# --------------------- Старт ---------------------
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(texts.START_TEXT, reply_markup=kb.main_menu_kb())

# --------------------- Отмена ---------------------
@dp.message(Text("❌ Отмена"))
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.CANCEL_TEXT, reply_markup=kb.main_menu_kb())

# --------------------- Админ-панель ---------------------
@dp.message(Text("🛠️ Админ-панель"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён!")
        return
    await message.answer(texts.ADMIN_TEXT, reply_markup=kb.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton("➕ Добавить категорию")],
            [types.KeyboardButton("➕ Добавить курс")]
        ],
        resize_keyboard=True
    ))

# --------------------- Добавление категории ---------------------
@dp.message(Text("➕ Добавить категорию"))
async def add_category_start(message: types.Message, state: FSMContext):
    await states.AddCategory.waiting_for_name.set()
    await message.answer("Введите название категории:", reply_markup=kb.cancel_kb())

@dp.message(states.AddCategory.waiting_for_name)
async def add_category_name(message: types.Message, state: FSMContext):
    await db.add_category(message.text)
    await state.clear()
    await message.answer(f"Категория '{message.text}' добавлена!", reply_markup=kb.main_menu_kb())

# --------------------- Просмотр категорий ---------------------
@dp.message(Text("📚 Курсы"))
async def show_categories(message: types.Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категории отсутствуют.")
        return
    await message.answer("Выберите категорию:", reply_markup=kb.category_kb(categories))

# --------------------- Просмотр курсов ---------------------
@dp.callback_query(lambda c: c.data.startswith("user_cat:"))
async def show_courses(call: types.CallbackQuery):
    cat_id = int(call.data.split(":")[1])
    courses = await db.get_courses_by_category(cat_id)
    if not courses:
        await call.message.answer("Курсы в этой категории отсутствуют.")
        return
    for course in courses:
        text = f"<b>{course[2]}</b>\n{course[3]}\n💰 Цена: {course[4]} RUB"
        await call.message.answer(text, reply_markup=kb.pay_kb(course[0]))

# --------------------- Оплата ---------------------
@dp.callback_query(lambda c: c.data.startswith("pay:"))
async def pay_course(call: types.CallbackQuery):
    course_id = int(call.data.split(":")[1])
    course = await db.get_course(course_id)
    if not course:
        await call.message.answer("Ошибка! Курс не найден.")
        return
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=course[2],
        description=course[3],
        payload=f"course_{course_id}",
        provider_token=os.getenv("PAYMENT_TOKEN"),  # Telegram Payment Token
        currency="RUB",
        prices=[types.LabeledPrice(label=course[2], amount=course[4]*100)]
    )

# --------------------- Обработка успешной оплаты ---------------------
@dp.pre_checkout_query()
async def checkout(pre_checkout: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)

@dp.message(types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    await message.answer("✅ Оплата прошла успешно! Курс доступен для обучения.")

# --------------------- Запуск ---------------------
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))





