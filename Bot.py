import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

import db
import keyboards as kb
from states import AddCategory, AddCourse, EditCourse

# ================= CONFIG =================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PAYMENTS_TOKEN = os.getenv("PAYMENTS_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())


# ================= START =================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "👋 Привет, смертный. Я — твой циничный наставник. "
        "Выбирай, что тебе нужно.",
        reply_markup=kb.main_menu(admin=is_admin)
    )


# ================= ABOUT =================
@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message):
    await message.answer(
        "Я — ИИ с философией и цинизмом. "
        "Я продаю знания, а ты решаешь, достоин ли ты их."
    )


# ================= CATEGORIES =================
@dp.message(F.text == "📚 Курсы")
async def list_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категорий нет. Похоже, знания пока недоступны.")
        return
    await message.answer("Выбирай категорию:", reply_markup=kb.categories_inline(categories))


@dp.callback_query(F.data.startswith("category_"))
async def list_courses(callback: CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    courses = await db.get_courses_by_category(cat_id)
    if not courses:
        await callback.message.edit_text("В этой категории пока пусто.")
        return

    for course in courses:
        text = (
            f"<b>{course['title']}</b>\n\n"
            f"{course['description']}\n\n"
            f"Цена: {course['price']} ₽"
        )
        pay_button = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"💳 Купить за {course['price']} ₽",
                                        callback_data=f"buy_{course['id']}")]
        ])
        await callback.message.answer(text, reply_markup=pay_button)


# ================= PAYMENTS =================
@dp.callback_query(F.data.startswith("buy_"))
async def buy_course(callback: CallbackQuery):
    course_id = int(callback.data.split("_")[1])
    course = await db.get_course(course_id)
    if not course:
        await callback.answer("Ошибка: курс не найден", show_alert=True)
        return

    prices = [LabeledPrice(label=course["title"], amount=course["price"] * 100)]

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course["title"],
        description=course["description"],
        payload=str(course["id"]),
        provider_token=PAYMENTS_TOKEN,
        currency="RUB",
        prices=prices,
    )


@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    course = await db.get_course(int(payload))
    if course:
        await message.answer(
            f"🎉 Оплата прошла успешно!\n\n"
            f"Вот твоя ссылка: {course['link']}"
        )


# ================= ADMIN PANEL =================
@dp.message(F.text == "👑 Админ")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Админ-панель:", reply_markup=kb.admin_menu())


# --- Categories ---
@dp.message(F.text == "➕ Добавить категорию")
async def add_category(message: Message, state: FSMContext):
    await state.set_state(AddCategory.waiting_for_title)
    await message.answer("Введи название категории:")


@dp.message(StateFilter(AddCategory.waiting_for_title))
async def save_category(message: Message, state: FSMContext):
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена.")


# --- Courses ---
@dp.message(F.text == "➕ Добавить курс")
async def add_course(message: Message, state: FSMContext):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Сначала добавь категорию.")
        return
    await state.set_state(AddCourse.waiting_for_title)
    await message.answer("Введи название курса:")


@dp.message(StateFilter(AddCourse.waiting_for_title))
async def save_course_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Теперь описание:")


@dp.message(StateFilter(AddCourse.waiting_for_description))
async def save_course_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Цена в рублях:")


@dp.message(StateFilter(AddCourse.waiting_for_price))
async def save_course_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("Введи число.")
        return
    await state.update_data(price=price)
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Ссылка на курс:")


@dp.message(StateFilter(AddCourse.waiting_for_link))
async def save_course_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    await state.set_state(AddCourse.waiting_for_category)

    categories = await db.get_categories()
    await message.answer("Выбери категорию:",
                         reply_markup=kb.categories_keyboard(categories))


@dp.message(StateFilter(AddCourse.waiting_for_category))
async def save_course_category(message: Message, state: FSMContext):
    data = await state.get_data()
    categories = await db.get_categories()
    cat = next((c for c in categories if c["title"] == message.text), None)
    if not cat:
        await message.answer("Неверная категория. Попробуй снова.")
        return

    await db.add_course(
        cat["id"], data["title"], data["description"], data["price"], data["link"]
    )
    await state.clear()
    await message.answer("Курс добавлен.")


# ================= RUN =================
async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
