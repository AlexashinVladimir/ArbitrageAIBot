import os
from dotenv import load_dotenv
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

import db
import keyboards as kb
import texts
import states

# --- Загружаем переменные из .env ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- Остальной код Bot.py без изменений ---
# (все функции start, админка, FSM, оплата, категории и курсы)

# --- Старт ---
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(texts.START_TEXT, reply_markup=kb.main_menu_kb())

# --- Просмотр категорий и курсов ---
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    categories = await db.list_categories()
    await message.answer("Выберите категорию:", reply_markup=kb.category_kb(categories))

@dp.callback_query(lambda c: c.data.startswith("user_cat:"))
async def show_courses(cb: CallbackQuery):
    cat_id = int(cb.data.split(":")[1])
    courses = await db.list_courses_by_category(cat_id)
    await cb.message.edit_text("Выберите курс:", reply_markup=kb.course_kb(courses))

@dp.callback_query(lambda c: c.data.startswith("course:"))
async def course_details(cb: CallbackQuery):
    course_id = int(cb.data.split(":")[1])
    course = await db.get_course(course_id)
    if not course:
        await cb.message.edit_text("Курс не найден")
        return
    text = f"📌 {course[2]}\n\n{course[3]}\n\nЦена: {course[4]} {course[5]}"
    await cb.message.edit_text(text, reply_markup=kb.pay_kb(course_id))

# --- Оплата Telegram ---
@dp.callback_query(lambda c: c.data.startswith("pay:"))
async def pay_course(cb: CallbackQuery):
    course_id = int(cb.data.split(":")[1])
    course = await db.get_course(course_id)
    await bot.send_invoice(
        cb.from_user.id,
        title=course[2],
        description=course[3],
        provider_token="ВАШ_ПРОВАЙДЕР_ТОКЕН",
        currency=course[5],
        start_parameter="payment",
        payload=str(course_id),
        prices=[{"label": course[2], "amount": int(course[4]*100)}]
    )

@dp.message(F.content_type == "successful_payment")
async def payment_success(message: Message):
    course_id = int(message.successful_payment.invoice_payload)
    await db.add_payment(
        user_id=message.from_user.id,
        course_id=course_id,
        amount=message.successful_payment.total_amount/100,
        currency=message.successful_payment.currency,
        telegram_charge_id=message.successful_payment.telegram_payment_charge_id,
        provider_charge_id=message.successful_payment.provider_payment_charge_id
    )
    await message.answer("✅ Оплата прошла успешно!")

# --- Рекомендации ИИ ---
@dp.message(F.text == "💡 Рекомендации ИИ")
async def ai_advice(message: Message):
    await message.answer(random.choice(texts.AI_RECOMMENDATION))

# --- Админка ---
@dp.message(F.text == "🛠️ Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа")
        return
    await message.answer(texts.ADMIN_TEXT, reply_markup=kb.admin_kb())

# --- Управление категориями ---
@dp.message(F.text == "📂 Управление категориями")
async def manage_categories(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    categories = await db.list_categories()
    await message.answer("Управление категориями:", reply_markup=kb.admin_categories_kb(categories))

@dp.callback_query(lambda c: c.data.startswith("toggle_cat:"))
async def toggle_category(cb: CallbackQuery):
    cat_id = int(cb.data.split(":")[1])
    await db.toggle_category(cat_id)
    categories = await db.list_categories()
    await cb.message.edit_text("Категории обновлены:", reply_markup=kb.admin_categories_kb(categories))

# --- Управление курсами ---
@dp.message(F.text == "📚 Управление курсами")
async def manage_courses(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    courses = await db.list_all_courses()
    await message.answer("Управление курсами:", reply_markup=kb.admin_courses_kb(courses))

@dp.callback_query(lambda c: c.data.startswith("toggle_course:"))
async def toggle_course(cb: CallbackQuery):
    course_id = int(cb.data.split(":")[1])
    await db.toggle_course(course_id)
    courses = await db.list_all_courses()
    await cb.message.edit_text("Курсы обновлены:", reply_markup=kb.admin_courses_kb(courses))

# --- Добавление категории ---
@dp.message(F.text == "➕ Добавить категорию")
async def add_category_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(states.AddCategory.waiting_name)
    await message.answer("Введите название категории:", reply_markup=kb.cancel_kb())

@dp.message(states.AddCategory.waiting_name)
async def add_category_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление категории отменено", reply_markup=kb.admin_kb())
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена!", reply_markup=kb.admin_kb())

# --- Добавление курса (FSM) ---
@dp.message(F.text == "➕ Добавить курс")
async def add_course_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    categories = await db.list_categories()
    active_cats = [c for c in categories if c[2]]
    if not active_cats:
        await message.answer("Сначала добавьте хотя бы одну категорию")
        return
    await state.set_state(states.AddCourse.waiting_category)
    await state.update_data(categories=active_cats)
    kb_inline = kb.InlineKeyboardMarkup(
        inline_keyboard=[[kb.InlineKeyboardButton(c[1], callback_data=f"newcourse_cat:{c[0]}")] for c in active_cats]
    )
    await message.answer("Выберите категорию для нового курса:", reply_markup=kb_inline)

@dp.callback_query(lambda c: c.data.startswith("newcourse_cat:"))
async def add_course_category(cb: CallbackQuery, state: FSMContext):
    cat_id = int(cb.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(states.AddCourse.waiting_title)
    await cb.message.edit_text("Введите название курса:", reply_markup=kb.cancel_kb())

@dp.message(states.AddCourse.waiting_title)
async def add_course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление курса отменено", reply_markup=kb.admin_kb())
        return
    await state.update_data(title=message.text)
    await state.set_state(states.AddCourse.waiting_description)
    await message.answer("Введите описание курса:", reply_markup=kb.cancel_kb())

@dp.message(states.AddCourse.waiting_description)
async def add_course_description(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление курса отменено", reply_markup=kb.admin_kb())
        return
    await state.update_data(description=message.text)
    await state.set_state(states.AddCourse.waiting_price)
    await message.answer("Введите цену курса (числом):", reply_markup=kb.cancel_kb())

@dp.message(states.AddCourse.waiting_price)
async def add_course_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление курса отменено", reply_markup=kb.admin_kb())
        return
    try:
        price = float(message.text)
    except:
        await message.answer("Введите корректное число")
        return
    await state.update_data(price=price)
    await state.set_state(states.AddCourse.waiting_link)
    await message.answer("Введите ссылку на курс:", reply_markup=kb.cancel_kb())

@dp.message(states.AddCourse.waiting_link)
async def add_course_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление курса отменено", reply_markup=kb.admin_kb())
        return
    data = await state.get_data()
    await db.add_course(
        category_id=data['category_id'],
        title=data['title'],
        description=data['description'],
        price=data['price'],
        currency="RUB",
        link=message.text
    )
    await state.clear()
    await message.answer("Курс добавлен!", reply_markup=kb.admin_kb())

# --- Запуск ---
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    dp.run_polling(bot)






