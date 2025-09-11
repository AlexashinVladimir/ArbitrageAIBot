# Bot.py
import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

import db
import keyboards as kb
from states import AddCategory, AddCourse, EditCourse

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PAYMENTS_PROVIDER_TOKEN = os.getenv("PAYMENTS_PROVIDER_TOKEN")  # тестовый токен от @BotFather

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()


# ------------------------- Старт -------------------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await db.init_db()
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "Привет, человек. Я циничный ИИ. Курсы помогут тебе стать менее жалкой версией себя.",
        reply_markup=kb.main_menu(admin=is_admin),
    )


# ------------------------- Пользовательская часть -------------------------
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категорий нет. Видимо, человечество решило остаться глупым.")
        return
    await message.answer("Выбирай категорию:", reply_markup=kb.categories_inline(categories))


@dp.callback_query(F.data.startswith("category_"))
async def show_courses(callback: CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    courses = await db.get_courses_by_category(cat_id)
    if not courses:
        await callback.message.answer("Здесь пусто. Знания тоже имеют границы.")
        return
    for course in courses:
        text = f"<b>{course['title']}</b>\n\n{course['description']}\n\nЦена: {course['price']} ₽"
        await callback.message.answer(text, reply_markup=kb.course_inline(course))
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_"))
async def buy_course(callback: CallbackQuery):
    course_id = int(callback.data.split("_")[1])
    course = await db.get_course(course_id)
    if not course:
        await callback.answer("Курс не найден.", show_alert=True)
        return

    prices = [LabeledPrice(label=course["title"], amount=course["price"] * 100)]  # в копейках

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course["title"],
        description=course["description"],
        payload=f"course_{course_id}",
        provider_token=PAYMENTS_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter="test-payment",
    )
    await callback.answer()


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("course_"):
        course_id = int(payload.split("_")[1])
        course = await db.get_course(course_id)
        if course:
            await message.answer(
                f"Поздравляю, ты купил <b>{course['title']}</b>.\n\nВот твоя ссылка: {course['link']}"
            )


@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message):
    await message.answer("Я бот-ментор. Немного философ, немного циник. Готов ломать твои иллюзии.")


# ------------------------- Админская панель -------------------------
@dp.message(F.text == "⚙️ Админ")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Добро пожаловать в админ-панель.", reply_markup=kb.admin_menu)


# ---- Добавить категорию ----
@dp.message(F.text == "➕ Добавить категорию")
async def admin_add_category(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddCategory.waiting_for_title)
    await message.answer("Введи название категории:", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(AddCategory.waiting_for_title))
async def admin_save_category(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu)
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена.", reply_markup=kb.admin_menu)


# ---- Добавить курс ----
@dp.message(F.text == "➕ Добавить курс")
async def admin_add_course(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    categories = await db.get_categories()
    if not categories:
        await message.answer("Сначала добавь категорию.")
        return
    await state.set_state(AddCourse.waiting_for_category)
    buttons = [[c["title"]] for c in categories]
    markup = kb.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("Выбери категорию:", reply_markup=markup)


@dp.message(StateFilter(AddCourse.waiting_for_category))
async def admin_add_course_title(message: Message, state: FSMContext):
    categories = await db.get_categories()
    category = next((c for c in categories if c["title"] == message.text), None)
    if not category:
        await message.answer("Такой категории нет. Попробуй снова.")
        return
    await state.update_data(category_id=category["id"])
    await state.set_state(AddCourse.waiting_for_title)
    await message.answer("Введи название курса:", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(AddCourse.waiting_for_title))
async def admin_add_course_desc(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu)
        return
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Введи описание курса:")


@dp.message(StateFilter(AddCourse.waiting_for_description))
async def admin_add_course_price(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Введи цену (в рублях):")


@dp.message(StateFilter(AddCourse.waiting_for_price))
async def admin_add_course_link(message: Message, state: FSMContext):
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("Цена должна быть числом.")
        return
    await state.update_data(price=price)
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Введи ссылку на курс:")


@dp.message(StateFilter(AddCourse.waiting_for_link))
async def admin_save_course(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_course(
        data["category_id"],
        data["title"],
        data["description"],
        data["price"],
        message.text,
    )
    await state.clear()
    await message.answer("Курс добавлен.", reply_markup=kb.admin_menu)


# ---- Управление курсами ----
@dp.message(F.text == "📂 Управление курсами")
async def admin_manage_courses(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    courses = await db.get_courses()
    if not courses:
        await message.answer("Курсов нет.")
        return
    await message.answer("Выбери курс:", reply_markup=kb.admin_courses_inline(courses))


@dp.callback_query(F.data.startswith("admin_course_"))
async def admin_course_menu(callback: CallbackQuery):
    course_id = int(callback.data.split("_")[2])
    await callback.message.answer("Выбери действие:", reply_markup=kb.course_admin_inline(course_id))
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_course_"))
async def admin_delete_course(callback: CallbackQuery):
    course_id = int(callback.data.split("_")[2])
    await db.delete_course(course_id)
    await callback.message.answer("Курс удалён.")
    await callback.answer()


# ---- Редактирование курса ----
@dp.callback_query(F.data.startswith("edit_course_"))
async def admin_edit_course(callback: CallbackQuery, state: FSMContext):
    course_id = int(callback.data.split("_")[2])
    await state.update_data(course_id=course_id)
    await state.set_state(EditCourse.waiting_for_new_title)
    await callback.message.answer("Введи новое название курса:", reply_markup=kb.cancel_kb)
    await callback.answer()


@dp.message(StateFilter(EditCourse.waiting_for_new_title))
async def edit_course_title(message: Message, state: FSMContext):
    await state.update_data(new_title=message.text)
    await state.set_state(EditCourse.waiting_for_new_description)
    await message.answer("Введи новое описание курса:")


@dp.message(StateFilter(EditCourse.waiting_for_new_description))
async def edit_course_description(message: Message, state: FSMContext):
    await state.update_data(new_description=message.text)
    await state.set_state(EditCourse.waiting_for_new_price)
    await message.answer("Введи новую цену (в рублях):")


@dp.message(StateFilter(EditCourse.waiting_for_new_price))
async def edit_course_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("Цена должна быть числом.")
        return
    await state.update_data(new_price=price)
    await state.set_state(EditCourse.waiting_for_new_link)
    await message.answer("Введи новую ссылку на курс:")


@dp.message(StateFilter(EditCourse.waiting_for_new_link))
async def edit_course_link(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.update_course(
        data["course_id"],
        data["new_title"],
        data["new_description"],
        data["new_price"],
        message.text,
    )
    await state.clear()
    await message.answer("Курс обновлён.", reply_markup=kb.admin_menu)


# ------------------------- RUN -------------------------
async def main():
    await db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())



