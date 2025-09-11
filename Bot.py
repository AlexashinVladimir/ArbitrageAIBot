import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

import db
import keyboards as kb

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())


# FSM для категорий
class CategoryStates(StatesGroup):
    waiting_for_title = State()


# FSM для курсов
class CourseStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_link = State()


# Команда /start
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "Добро пожаловать в этот слегка циничный, но мудрый уголок ИИ.\n"
        "Здесь ты можешь приобрести курсы или узнать больше обо мне.",
        reply_markup=kb.main_menu(is_admin=is_admin),
    )


# О боте
@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message):
    await message.answer(
        "Я — твой циничный наставник. "
        "Не обещаю, что будет легко. Но обещаю, что будет честно."
    )


# --- Управление категориями ---
@dp.message(F.text == "➕ Добавить категорию")
async def add_category(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введи название новой категории:", reply_markup=kb.cancel())
    await state.set_state(CategoryStates.waiting_for_title)


@dp.message(CategoryStates.waiting_for_title)
async def save_category(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление категории отменено.", reply_markup=kb.admin_panel())
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer(f"✅ Категория <b>{message.text}</b> добавлена.", reply_markup=kb.admin_panel())


# --- Управление курсами ---
@dp.message(F.text == "➕ Добавить курс")
async def add_course(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    categories = await db.get_categories()
    if not categories:
        await message.answer("❌ Сначала добавь хотя бы одну категорию.", reply_markup=kb.admin_panel())
        return
    await message.answer("Выбери категорию:", reply_markup=kb.categories_inline(categories))
    await state.set_state(CourseStates.waiting_for_category)


@dp.callback_query(CourseStates.waiting_for_category)
async def course_set_category(callback: CallbackQuery, state: FSMContext):
    await state.update_data(category_id=int(callback.data.split("_")[1]))
    await callback.message.answer("Введи название курса:", reply_markup=kb.cancel())
    await state.set_state(CourseStates.waiting_for_title)


@dp.message(CourseStates.waiting_for_title)
async def course_set_title(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление курса отменено.", reply_markup=kb.admin_panel())
        return
    await state.update_data(title=message.text)
    await message.answer("Теперь введи описание:", reply_markup=kb.cancel())
    await state.set_state(CourseStates.waiting_for_description)


@dp.message(CourseStates.waiting_for_description)
async def course_set_description(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление курса отменено.", reply_markup=kb.admin_panel())
        return
    await state.update_data(description=message.text)
    await message.answer("Укажи цену в рублях:", reply_markup=kb.cancel())
    await state.set_state(CourseStates.waiting_for_price)


@dp.message(CourseStates.waiting_for_price)
async def course_set_price(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление курса отменено.", reply_markup=kb.admin_panel())
        return
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("⚠️ Введи число для цены.")
        return
    await state.update_data(price=price)
    await message.answer("Вставь ссылку на курс:", reply_markup=kb.cancel())
    await state.set_state(CourseStates.waiting_for_link)


@dp.message(CourseStates.waiting_for_link)
async def course_set_link(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Добавление курса отменено.", reply_markup=kb.admin_panel())
        return
    data = await state.get_data()
    await db.add_course(
        data["category_id"], data["title"], data["description"], data["price"], message.text
    )
    await state.clear()
    await message.answer(f"✅ Курс <b>{data['title']}</b> добавлен.", reply_markup=kb.admin_panel())


# --- Просмотр категорий и курсов ---
@dp.message(F.text == "📚 Категории")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категорий пока нет.")
        return
    await message.answer("Выбери категорию:", reply_markup=kb.categories_inline(categories))


@dp.callback_query(F.data.startswith("cat_"))
async def show_courses(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    courses = await db.get_courses(category_id)
    if not courses:
        await callback.message.answer("❌ В этой категории пока нет курсов.")
        return
    await callback.message.answer("Доступные курсы:", reply_markup=kb.courses_inline(courses))


@dp.callback_query(F.data.startswith("course_"))
async def show_course(callback: CallbackQuery):
    course_id = int(callback.data.split("_")[1])
    course = await db.get_course(course_id)
    if not course:
        await callback.message.answer("⚠️ Курс не найден.")
        return
    text = f"<b>{course['title']}</b>\n\n{course['description']}\n\nЦена: {course['price']}₽"
    await callback.message.answer(
        text,
        reply_markup=kb.buy_course(course["id"], course["price"], course["title"]),
    )


# --- Оплата ---
@dp.callback_query(F.data.startswith("buy_"))
async def process_payment(callback: CallbackQuery):
    _, course_id, price, title = callback.data.split("_", 3)
    prices = [LabeledPrice(label=title, amount=int(price) * 100)]
    await bot.send_invoice(
        callback.from_user.id,
        title=title,
        description="Доступ к курсу",
        provider_token=PAYMENT_PROVIDER,
        currency="rub",
        prices=prices,
        payload=f"course_{course_id}",
    )


@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message(F.content_type == "successful_payment")
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    course_id = int(payload.split("_")[1])
    course = await db.get_course(course_id)
    await message.answer(
        f"✅ Оплата прошла успешно!\n\nВот твоя ссылка: {course['link']}"
    )


# --- Запуск бота ---
async def main():
    await db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())




