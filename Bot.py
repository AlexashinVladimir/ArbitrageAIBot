import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

import db
import keyboards as kb


# Загрузка конфигурации
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PAYMENTS_PROVIDER_TOKEN = os.getenv("PAYMENTS_PROVIDER_TOKEN")

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())


# FSM состояния
class CategoryStates(StatesGroup):
    waiting_for_title = State()


class CourseStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ---------- Основные команды ----------

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Это бот курсов.",
        reply_markup=kb.main_menu(is_admin(message.from_user.id == ADMIN_ID))
    )


@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message):
    await message.answer("📌 Этот бот позволяет покупать курсы прямо в Telegram.")


# ---------- Работа с категориями ----------

@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Пока нет категорий.")
    else:
        await message.answer("Выберите категорию:", reply_markup=kb.categories_inline(categories))


@dp.callback_query(F.data.startswith("category:"))
async def show_courses(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    courses = await db.get_courses(cat_id)
    if not courses:
        await callback.message.edit_text("В этой категории пока нет курсов.")
    else:
        for c in courses:
            text = f"<b>{c['title']}</b>\n\n{c['description']}"
            await callback.message.answer(text, reply_markup=kb.courses_inline([c]))
    await callback.answer()


# ---------- Покупка ----------

@dp.callback_query(F.data.startswith("buy:"))
async def buy_course(callback: CallbackQuery):
    course_id = int(callback.data.split(":")[1])
    course = await db.get_course(course_id)

    if not course:
        await callback.answer("Курс не найден.", show_alert=True)
        return

    prices = [LabeledPrice(label=course['title'], amount=int(course['price']) * 100)]
    await bot.send_invoice(
        callback.message.chat.id,
        title=course['title'],
        description=course['description'],
        payload=f"course_{course['id']}",
        provider_token=PAYMENTS_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices
    )
    await callback.answer()


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)


@dp.message(F.content_type == "successful_payment")
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    course_id = int(payload.split("_")[1])
    course = await db.get_course(course_id)
    await message.answer(f"✅ Оплата прошла успешно!\nВот ваш курс: {course['title']}")


# ---------- Админ-панель ----------

@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🔐 Админ-панель", reply_markup=kb.admin_menu())


# Добавление категории
@dp.message(F.text == "➕ Добавить категорию")
async def add_category(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Введите название категории:", reply_markup=kb.cancel_kb())
    await state.set_state(CategoryStates.waiting_for_title)


@dp.message(CategoryStates.waiting_for_title)
async def save_category(message: Message, state: FSMContext):
    await db.add_category(message.text)
    await message.answer("✅ Категория добавлена.", reply_markup=kb.admin_menu())
    await state.clear()


# Добавление курса
@dp.message(F.text == "➕ Добавить курс")
async def add_course(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    categories = await db.get_categories()
    if not categories:
        await message.answer("❌ Сначала добавьте категорию.")
        return
    kb_cats = kb.categories_inline(categories)
    await message.answer("Выберите категорию для курса:", reply_markup=kb_cats)
    await state.set_state(CourseStates.waiting_for_category)


@dp.callback_query(CourseStates.waiting_for_category, F.data.startswith("category:"))
async def course_set_category(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await callback.message.answer("Введите название курса:", reply_markup=kb.cancel_kb())
    await state.set_state(CourseStates.waiting_for_title)
    await callback.answer()


@dp.message(CourseStates.waiting_for_title)
async def course_set_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введите описание курса:", reply_markup=kb.cancel_kb())
    await state.set_state(CourseStates.waiting_for_description)


@dp.message(CourseStates.waiting_for_description)
async def course_set_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите цену курса (в ₽):", reply_markup=kb.cancel_kb())
    await state.set_state(CourseStates.waiting_for_price)


@dp.message(CourseStates.waiting_for_price)
async def course_set_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Цена должна быть числом.")
        return
    data = await state.get_data()
    await db.add_course(
        data["category_id"], data["title"], data["description"], int(message.text)
    )
    await message.answer("✅ Курс добавлен.", reply_markup=kb.admin_menu())
    await state.clear()


# Управление категориями
@dp.message(F.text == "📂 Управление категориями")
async def manage_categories(message: Message):
    if not is_admin(message.from_user.id):
        return
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категорий нет.", reply_markup=kb.admin_menu())
        return
    await message.answer("Категории:", reply_markup=kb.edit_delete_inline("category", categories))


# Управление курсами
@dp.message(F.text == "📘 Управление курсами")
async def manage_courses(message: Message):
    if not is_admin(message.from_user.id):
        return
    courses = await db.get_all_courses()
    if not courses:
        await message.answer("Курсов нет.", reply_markup=kb.admin_menu())
        return
    await message.answer("Курсы:", reply_markup=kb.edit_delete_inline("course", courses))


# Назад из меню
@dp.message(F.text == "⬅️ Назад")
async def back_from_admin(message: Message):
    if is_admin(message.from_user.id):
        await message.answer("⬅️ Возврат в главное меню.", reply_markup=kb.main_menu(True))
    else:
        await message.answer("⬅️ Возврат в главное меню.", reply_markup=kb.main_menu(False))


# Отмена любого действия
@dp.message(F.text == "❌ Отмена")
async def cancel_any(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🚫 Действие отменено.", reply_markup=kb.admin_menu())


# Inline назад
@dp.callback_query(F.data == "back_to_admin")
async def back_inline_admin(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("⬅️ Возврат в админ-панель.", reply_markup=kb.admin_menu())


# ---------- Запуск ----------

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


