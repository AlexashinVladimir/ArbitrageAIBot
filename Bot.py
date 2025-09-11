import asyncio
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import db
import keyboards as kb

# --- Загружаем токен и ADMIN_ID из .env ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# --- Состояния FSM ---
class AddCategory(StatesGroup):
    waiting_for_title = State()


class AddCourse(StatesGroup):
    waiting_for_category = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_link = State()


class EditCourse(StatesGroup):
    waiting_for_field = State()
    waiting_for_value = State()


# --- Старт ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "Добро пожаловать. Я — бот-куратор. Выбирай:",
        reply_markup=kb.main_menu(is_admin)
    )


# --- О боте ---
@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message):
    await message.answer(
        "Я — твой немного циничный наставник.\n"
        "Помогаю покупать курсы, а иногда — становиться лучше."
    )


# --- Категории и курсы ---
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категорий пока нет.")
    else:
        await message.answer("Выбери категорию:", reply_markup=kb.categories_keyboard(categories))


@dp.callback_query(F.data.startswith("category:"))
async def show_courses(callback: CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    courses = await db.get_courses(category_id)
    if not courses:
        await callback.message.answer("В этой категории пока нет курсов.")
    else:
        for course in courses:
            text = f"<b>{course['title']}</b>\n\n{course['description']}\n\nЦена: {course['price']} ₽"
            await callback.message.answer(
                text,
                reply_markup=kb.course_keyboard(course["id"], course["price"], course["title"])
            )
    await callback.answer()


# --- Оплата ---
@dp.callback_query(F.data.startswith("buy:"))
async def process_buy(callback: CallbackQuery):
    course_id = int(callback.data.split(":")[1])
    course = await db.get_course(course_id)
    if not course:
        await callback.answer("Ошибка: курс не найден.", show_alert=True)
        return

    prices = [LabeledPrice(label=course["title"], amount=course["price"] * 100)]

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course["title"],
        description=course["description"],
        payload=str(course["id"]),
        provider_token=os.getenv("PAYMENT_PROVIDER_TOKEN"),
        currency="RUB",
        prices=prices
    )
    await callback.answer()


@dp.pre_checkout_query()
async def pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message(F.content_type == "successful_payment")
async def successful_payment(message: Message):
    course_id = int(message.successful_payment.invoice_payload)
    course = await db.get_course(course_id)
    if course:
        await message.answer(
            f"Оплата прошла успешно! 🎉\n\nВот ссылка на курс:\n{course['link']}"
        )


# --- Админ-панель ---
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Админ-панель:", reply_markup=kb.admin_menu())


# --- Управление категориями ---
@dp.callback_query(F.data == "admin_add_category")
async def admin_add_category(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddCategory.waiting_for_title)
    await callback.message.answer("Введи название категории:", reply_markup=kb.cancel_keyboard())
    await callback.answer()


@dp.message(StateFilter(AddCategory.waiting_for_title))
async def save_category(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление категории отменено.", reply_markup=kb.admin_menu())
        return

    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена.", reply_markup=kb.admin_menu())


# --- Управление курсами ---
@dp.callback_query(F.data == "admin_add_course")
async def admin_add_course(callback: CallbackQuery, state: FSMContext):
    categories = await db.get_categories()
    if not categories:
        await callback.message.answer("Сначала добавь категорию.")
        return
    await state.set_state(AddCourse.waiting_for_category)
    await callback.message.answer("Выбери категорию:", reply_markup=kb.categories_keyboard(categories, admin=True))
    await callback.answer()


@dp.callback_query(StateFilter(AddCourse.waiting_for_category))
async def select_course_category(callback: CallbackQuery, state: FSMContext):
    if callback.data == "cancel":
        await state.clear()
        await callback.message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    category_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=category_id)
    await state.set_state(AddCourse.waiting_for_title)
    await callback.message.answer("Введи название курса:", reply_markup=kb.cancel_keyboard())
    await callback.answer()


@dp.message(StateFilter(AddCourse.waiting_for_title))
async def course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Введи описание курса:", reply_markup=kb.cancel_keyboard())


@dp.message(StateFilter(AddCourse.waiting_for_description))
async def course_description(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Введи цену курса (в рублях):", reply_markup=kb.cancel_keyboard())


@dp.message(StateFilter(AddCourse.waiting_for_price))
async def course_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    if not message.text.isdigit():
        await message.answer("Введите корректное число (только цифры).")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Введи ссылку на курс:", reply_markup=kb.cancel_keyboard())


@dp.message(StateFilter(AddCourse.waiting_for_link))
async def course_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    data = await state.get_data()
    await db.add_course(
        title=data["title"],
        description=data["description"],
        price=data["price"],
        link=message.text,
        category_id=data["category_id"]
    )
    await state.clear()
    await message.answer("Курс успешно добавлен.", reply_markup=kb.admin_menu())


# --- Отмена на всякий случай ---
@dp.message(F.text == "❌ Отмена")
async def cancel_action(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=kb.admin_menu())


# --- Запуск ---
async def main():
    await db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())






