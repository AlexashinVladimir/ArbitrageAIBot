import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command, StateFilter
from dotenv import load_dotenv

import keyboards as kb
import db


# ------------------- ЛОГИ -------------------
logging.basicConfig(level=logging.INFO)

# ------------------- НАСТРОЙКИ -------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# ------------------- СОСТОЯНИЯ -------------------
class AddCategory(StatesGroup):
    waiting_for_name = State()


class AddCourse(StatesGroup):
    choosing_category = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_link = State()


# ------------------- СТАРТ -------------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "👋 Привет! Я твой помощник по обучающим курсам.",
        reply_markup=kb.main_menu(is_admin)
    )


# ------------------- ПРОСМОТР КАТЕГОРИЙ -------------------
@dp.message(F.text == "📂 Категории")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категорий пока нет.")
        return
    await message.answer("Выберите категорию:", reply_markup=kb.categories_kb(categories))


@dp.callback_query(F.data.startswith("catview:"))
async def show_courses(callback: CallbackQuery):
    cid = int(callback.data.split(":")[1])
    courses = await db.get_courses(cid)
    if not courses:
        await callback.message.answer("В этой категории пока нет курсов.")
        return
    for course in courses:
        text = f"<b>{course['title']}</b>\n\n{course['description']}"
        price = [LabeledPrice(label=course["title"], amount=course["price"] * 100)]
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=course["title"],
            description=course["description"],
            payload=f"course_{course['id']}",
            provider_token=PROVIDER_TOKEN,
            currency="RUB",
            prices=price
        )


# ------------------- О БОТЕ -------------------
@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message):
    await message.answer("🤖 Я немного циничный ИИ с философией. "
                         "Помогаю тебе становиться лучшей версией себя.")


# ------------------- АДМИН ПАНЕЛЬ -------------------
@dp.message(F.text == "⚙️ Админ панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 У тебя нет доступа.")
        return
    await message.answer("⚙️ Панель управления:", reply_markup=kb.admin_panel())


# --- категории
@dp.message(F.text == "📁 Управление категориями")
async def manage_categories(message: Message):
    cats = await db.get_categories()
    text = "Категории:\n" + "\n".join([c["name"] for c in cats]) if cats else "Категорий пока нет."
    await message.answer(text + "\n\nОтправь название новой категории:", reply_markup=kb.cancel_kb())
    await dp.fsm.set_state(AddCategory.waiting_for_name)


@dp.message(StateFilter(AddCategory.waiting_for_name))
async def save_category(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("🚫 Отменено.", reply_markup=kb.main_menu(message.from_user.id == ADMIN_ID))
        await state.clear()
        return
    await db.add_category(message.text)
    await message.answer("✅ Категория добавлена!", reply_markup=kb.main_menu(True))
    await state.clear()


# --- курсы
@dp.message(F.text == "🎓 Управление курсами")
async def manage_courses(message: Message, state: FSMContext):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Сначала добавьте категории.")
        return
    await message.answer("Выберите категорию для курса:", reply_markup=kb.categories_kb(categories, for_add=True))
    await state.set_state(AddCourse.choosing_category)


@dp.callback_query(StateFilter(AddCourse.choosing_category), F.data.startswith("catadd:"))
async def choose_cat_for_course(callback: CallbackQuery, state: FSMContext):
    cid = int(callback.data.split(":")[1])
    await state.update_data(category_id=cid)
    await state.set_state(AddCourse.waiting_for_title)
    await callback.message.answer("Введите название курса:", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(AddCourse.waiting_for_title))
async def course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("🚫 Отменено.", reply_markup=kb.main_menu(True))
        await state.clear()
        return
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Введите описание курса:", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(AddCourse.waiting_for_description))
async def course_desc(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("🚫 Отменено.", reply_markup=kb.main_menu(True))
        await state.clear()
        return
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Введите цену (в рублях):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(AddCourse.waiting_for_price))
async def course_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("🚫 Отменено.", reply_markup=kb.main_menu(True))
        await state.clear()
        return
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("Введите число!")
        return
    await state.update_data(price=price)
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Отправьте ссылку на курс:", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(AddCourse.waiting_for_link))
async def course_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("🚫 Отменено.", reply_markup=kb.main_menu(True))
        await state.clear()
        return
    data = await state.get_data()
    await db.add_course(data["category_id"], data["title"], data["description"], data["price"], message.text)
    await message.answer("✅ Курс добавлен!", reply_markup=kb.main_menu(True))
    await state.clear()


# ------------------- ОПЛАТА -------------------
@dp.pre_checkout_query()
async def checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message(F.successful_payment)
async def got_payment(message: Message):
    await message.answer("💸 Спасибо за оплату! Вот твой курс. Ссылка отправлена отдельно.")


# ------------------- ЗАПУСК -------------------
async def main():
    await db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


