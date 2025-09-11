import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

import keyboards as kb
import db


logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PAYMENTS_TOKEN = os.getenv("PAYMENTS_TOKEN")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# --- FSM для добавления курса ---
class AddCourse(StatesGroup):
    waiting_for_category = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_link = State()


# --- Команда старт ---
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "Привет, смертный 👋\n\nЯ твой циничный наставник. "
        "Могу предложить тебе кое-что ценное... если осмелишься.",
        reply_markup=kb.main_menu(is_admin)
    )


# --- О боте ---
@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message):
    await message.answer(
        "Я не просто бот. Я твой философ с намёком на иронию.\n\n"
        "Помогу купить знания, которые либо сделают тебя сильнее, "
        "либо ещё глубже осознаешь бессмысленность всего вокруг."
    )


# --- Категории ---
@dp.message(F.text == "📚 Категории")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категорий пока нет.")
    else:
        await message.answer("Выбери категорию:", reply_markup=kb.categories_keyboard(categories))


@dp.callback_query(F.data.startswith("category_"))
async def show_courses(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    courses = await db.get_courses(category_id)
    if not courses:
        await callback.message.edit_text("В этой категории пока пусто.")
    else:
        for course in courses:
            text = f"<b>{course['title']}</b>\n\n{course['description']}\n\nЦена: {course['price']} ₽"
            await callback.message.answer(
                text,
                reply_markup=kb.course_keyboard(course['id'], course['price'])
            )
    await callback.answer()


# --- Оплата ---
@dp.callback_query(F.data.startswith("buy_"))
async def buy_course(callback: CallbackQuery):
    course_id, price = callback.data.split("_")[1:]
    price = int(price)

    await bot.send_invoice(
        callback.message.chat.id,
        title="Оплата курса",
        description="После оплаты ты получишь ссылку.",
        provider_token=PAYMENTS_TOKEN,
        currency="rub",
        prices=[LabeledPrice(label="Курс", amount=price * 100)],
        payload=f"course_{course_id}"
    )
    await callback.answer()


@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)


@dp.message(F.content_type == "successful_payment")
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    course_id = int(payload.split("_")[1])

    # достаём ссылку
    categories = await db.get_categories()
    for cat in categories:
        courses = await db.get_courses(cat['id'])
        for c in courses:
            if c['id'] == course_id:
                await message.answer(f"Вот твоя ссылка: {c['link']}")
                return


# --- Админ панель ---
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Добро пожаловать, властелин хаоса:", reply_markup=kb.admin_menu())


# --- Управление категориями ---
@dp.callback_query(F.data == "add_category")
async def add_category(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введи название категории или жми Отмена.", reply_markup=kb.cancel_keyboard())
    await state.set_state("waiting_for_category_name")
    await callback.answer()


@dp.message(F.text, state="waiting_for_category_name")
async def save_category(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Добавление категории отменено.", reply_markup=kb.main_menu(True))
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена ✅", reply_markup=kb.main_menu(True))


# --- Добавление курса ---
@dp.callback_query(F.data == "add_course")
async def add_course(callback: CallbackQuery, state: FSMContext):
    categories = await db.get_categories()
    if not categories:
        await callback.message.answer("Сначала добавь категорию!")
        return
    await state.set_state(AddCourse.waiting_for_category)
    await callback.message.answer("Выбери категорию:", reply_markup=kb.categories_keyboard(categories))
    await callback.answer()


@dp.callback_query(F.data.startswith("category_"), AddCourse.waiting_for_category)
async def select_course_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    await state.update_data(category_id=category_id)
    await state.set_state(AddCourse.waiting_for_title)
    await callback.message.answer("Введи название курса:", reply_markup=kb.cancel_keyboard())
    await callback.answer()


@dp.message(AddCourse.waiting_for_title)
async def course_title(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Добавление курса отменено.", reply_markup=kb.main_menu(True))
        return
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Теперь введи описание курса:", reply_markup=kb.cancel_keyboard())


@dp.message(AddCourse.waiting_for_description)
async def course_description(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Добавление курса отменено.", reply_markup=kb.main_menu(True))
        return
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Цена курса в рублях:", reply_markup=kb.cancel_keyboard())


@dp.message(AddCourse.waiting_for_price)
async def course_price(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Добавление курса отменено.", reply_markup=kb.main_menu(True))
        return
    if not message.text.isdigit():
        await message.answer("Введи число!")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Ссылка на курс:", reply_markup=kb.cancel_keyboard())


@dp.message(AddCourse.waiting_for_link)
async def course_link(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Добавление курса отменено.", reply_markup=kb.main_menu(True))
        return
    data = await state.get_data()
    await db.add_course(data['category_id'], data['title'], data['description'], data['price'], message.text)
    await state.clear()
    await message.answer("Курс добавлен ✅", reply_markup=kb.main_menu(True))


# --- Запуск ---
async def main():
    await db.create_tables()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())






