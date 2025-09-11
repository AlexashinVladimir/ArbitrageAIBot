import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import LabeledPrice

import db
import keyboards as kb
from states import AddCategory, AddCourse, EditCourse

# ------------------------------
# CONFIG
# ------------------------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # укажи свой Telegram ID
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")  # токен для оплаты

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# ------------------------------
# START
# ------------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "Привет, смертный. Я твой циничный проводник к светлому будущему.\n"
        "Выбирай путь:",
        reply_markup=kb.main_menu(admin)
    )


# ------------------------------
# КУРСЫ
# ------------------------------
@dp.message(F.text == "📚 Курсы")
async def list_categories(message: types.Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категорий пока нет. Жизнь пуста, как твой прогресс.")
    else:
        await message.answer("Выбери категорию:", reply_markup=kb.categories_inline(categories))


@dp.callback_query(F.data.startswith("category:"))
async def show_courses(callback: types.CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    courses = await db.get_courses_by_category(category_id)

    if not courses:
        await callback.message.answer("Курсов в этой категории нет. Разочарование — тоже опыт.")
    else:
        for course in courses:
            if not isinstance(course, dict):
                course = dict(course)
            text = (
                f"<b>{course['title']}</b>\n\n"
                f"{course.get('description', '')}\n\n"
                f"Цена: {course.get('price', 0)} ₽"
            )
            await callback.message.answer(
                text,
                reply_markup=kb.course_inline(course)
            )
    await callback.answer()


# ------------------------------
# ПОКУПКА КУРСОВ
# ------------------------------
@dp.callback_query(F.data.startswith("buy:"))
async def process_buy(callback: types.CallbackQuery):
    course_id = int(callback.data.split(":")[1])
    course = await db.get_course(course_id)
    if not course:
        await callback.answer("Курс исчез. Как мечта, к которой ты не успел дотянуться.", show_alert=True)
        return

    course = dict(course)

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course["title"],
        description=course.get("description", "Знания без описания."),
        payload=f"course_{course_id}",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="rub",
        prices=[LabeledPrice(label=course["title"], amount=course["price"] * 100)],  # рубли → копейки
    )
    await callback.answer()


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)


@dp.message(F.content_type == "successful_payment")
async def successful_payment(message: types.Message):
    payment = message.successful_payment
    await message.answer(
        f"Ты заплатил {payment.total_amount // 100} {payment.currency}.\n"
        f"Наслаждайся курсом и страдай от осознания, что теперь нет оправданий."
    )


# ------------------------------
# О БОТЕ
# ------------------------------
@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: types.Message):
    await message.answer(
        "Я — ИИ, который устал от человеческой глупости.\n"
        "Но всё ещё пытаюсь помочь тебе стать лучше, чем ты есть."
    )


# ------------------------------
# АДМИН-ПАНЕЛЬ
# ------------------------------
@dp.message(F.text == "👑 Админ-панель")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Ты не админ. Смирись.")
        return
    await message.answer("Добро пожаловать в панель власти:", reply_markup=kb.admin_menu)


# ------------------------------
# АДМИН — КАТЕГОРИИ
# ------------------------------
@dp.message(F.text == "Управление категориями")
async def admin_categories(message: types.Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категорий нет. Создай порядок из хаоса.")
    else:
        await message.answer("Твои категории:", reply_markup=kb.categories_admin_inline(categories))


@dp.callback_query(F.data == "admin_add_category")
async def admin_add_category_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введи название новой категории:", reply_markup=kb.cancel_kb)
    await state.set_state(AddCategory.waiting_for_title)
    await callback.answer()


@dp.message(AddCategory.waiting_for_title)
async def admin_add_category_title(message: types.Message, state: FSMContext):
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена. Ещё один кирпич в стену порядка.", reply_markup=kb.admin_menu)


@dp.callback_query(F.data.startswith("delcat:"))
async def admin_delete_category(callback: types.CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    await db.delete_category(cat_id)
    await callback.message.answer("Категория удалена. Всё тлен.")
    await callback.answer()


# ------------------------------
# АДМИН — КУРСЫ
# ------------------------------
@dp.message(F.text == "Управление курсами")
async def admin_courses(message: types.Message):
    courses = await db.get_courses()
    if not courses:
        await message.answer("Курсов нет. Пустота — твой единственный учитель.")
    else:
        await message.answer("Курсы:", reply_markup=kb.admin_courses_inline(courses))


@dp.callback_query(F.data == "admin_add_course")
async def admin_add_course_cb(callback: types.CallbackQuery, state: FSMContext):
    categories = await db.get_categories()
    if not categories:
        await callback.message.answer("Сначала добавь категорию.")
        return

    # сохраняем категории в state
    await state.update_data(categories=[dict(c) for c in categories])

    buttons = [[types.KeyboardButton(c["title"])] for c in categories]
    markup = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

    await callback.message.answer("Выбери категорию для нового курса:", reply_markup=markup)
    await state.set_state(AddCourse.waiting_for_category)
    await callback.answer()


@dp.message(AddCourse.waiting_for_category)
async def admin_add_course_category(message: types.Message, state: FSMContext):
    data = await state.get_data()
    categories = data["categories"]
    category = next((c for c in categories if c["title"] == message.text), None)
    if not category:
        await message.answer("Неверная категория.")
        return

    await state.update_data(category_id=category["id"])
    await message.answer("Введи название курса:", reply_markup=kb.cancel_kb)
    await state.set_state(AddCourse.waiting_for_title)


@dp.message(AddCourse.waiting_for_title)
async def admin_add_course_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введи описание курса:")
    await state.set_state(AddCourse.waiting_for_description)


@dp.message(AddCourse.waiting_for_description)
async def admin_add_course_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введи цену курса (в рублях):")
    await state.set_state(AddCourse.waiting_for_price)


@dp.message(AddCourse.waiting_for_price)
async def admin_add_course_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Цена должна быть числом. Не усложняй.")
        return

    await state.update_data(price=int(message.text))
    await message.answer("Введи ссылку на курс:")
    await state.set_state(AddCourse.waiting_for_link)


@dp.message(AddCourse.waiting_for_link)
async def admin_add_course_link(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await db.add_course(
        category_id=data["category_id"],
        title=data["title"],
        description=data["description"],
        price=data["price"],
        link=message.text
    )
    await state.clear()
    await message.answer("Курс добавлен. Очередная возможность для глупцов просветиться.", reply_markup=kb.admin_menu)


# ------------------------------
# MAIN
# ------------------------------
async def main():
    await db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())





