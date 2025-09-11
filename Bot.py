import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, LabeledPrice
from aiogram.fsm.context import FSMContext

import keyboards as kb
import db

# Логирование
logging.basicConfig(level=logging.INFO)

# === CONFIG ===
BOT_TOKEN = "YOUR_BOT_TOKEN"  # замени на свой токен
PAYMENT_PROVIDER_TOKEN = "YOUR_PROVIDER_TOKEN"  # токен от платежки
ADMIN_IDS = [123456789]  # ID админов

# === BOT ===
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# --- Вспомогательная функция ---
def resolve(obj, name, default=None):
    """Безопасный getattr"""
    if not isinstance(name, str):
        return default
    return getattr(obj, name, default)

# === Хэндлеры ===
@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    is_admin = message.from_user.id in ADMIN_IDS
    await message.answer(
        "Привет, человек. Я твой циничный философ-ИИ. "
        "Помогу тебе не стать счастливым, а стать лучше.",
        reply_markup=kb.main_menu(is_admin)
    )

# --- Админка ---
@dp.message(F.text == "Админ панель")
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Ты не достоин входа сюда.")
        return
    await message.answer("Добро пожаловать в святая святых.", reply_markup=kb.admin_menu())

# Добавление категории
@dp.message(F.text == "Добавить категорию")
async def admin_add_category(message: Message, state: FSMContext):
    await state.set_state("waiting_for_category")
    await message.answer("Введи название новой категории:")

@dp.message(F.text, state="waiting_for_category")
async def save_category(message: Message, state: FSMContext):
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена.", reply_markup=kb.admin_menu())

# Добавление курса
@dp.message(F.text == "Добавить курс")
async def admin_add_course(message: Message, state: FSMContext):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Нет категорий. Сначала добавь категорию.")
        return
    await state.set_state("waiting_for_course_category")
    await message.answer("Выбери категорию:", reply_markup=kb.categories_keyboard(categories))

@dp.message(F.text, state="waiting_for_course_category")
async def add_course_title(message: Message, state: FSMContext):
    await state.update_data(category=message.text)
    await state.set_state("waiting_for_course_title")
    await message.answer("Введи название курса:")

@dp.message(F.text, state="waiting_for_course_title")
async def add_course_desc(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state("waiting_for_course_desc")
    await message.answer("Опиши курс:")

@dp.message(F.text, state="waiting_for_course_desc")
async def add_course_price(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await state.set_state("waiting_for_course_price")
    await message.answer("Укажи цену курса (в рублях):")

@dp.message(F.text.regexp(r"^\d+$"), state="waiting_for_course_price")
async def add_course_link(message: Message, state: FSMContext):
    await state.update_data(price=int(message.text))
    await state.set_state("waiting_for_course_link")
    await message.answer("Дай ссылку на курс:")

@dp.message(F.text, state="waiting_for_course_link")
async def save_course(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_course(
        category=data["category"],
        title=data["title"],
        desc=data["desc"],
        price=data["price"],
        link=message.text,
    )
    await state.clear()
    await message.answer("Курс добавлен.", reply_markup=kb.admin_menu())

# --- Покупка курсов ---
@dp.message(F.text == "Категории")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Категорий пока нет.")
        return
    await message.answer("Выбирай категорию:", reply_markup=kb.categories_keyboard(categories))

@dp.message()
async def show_courses(message: Message):
    category = message.text
    courses = await db.get_courses(category)
    if not courses:
        await message.answer("Курсов нет в этой категории.")
        return
    for course in courses:
        await message.answer(
            f"<b>{course['title']}</b>\n"
            f"{course['desc']}\n"
            f"Цена: {course['price']}₽",
            reply_markup=kb.buy_button(course["id"], course["price"])
        )

# --- Оплата ---
@dp.callback_query(F.data.startswith("buy_"))
async def buy_course(call: CallbackQuery):
    course_id = int(call.data.split("_")[1])
    course = await db.get_course(course_id)
    if not course:
        await call.message.answer("Курс не найден.")
        return

    price = [LabeledPrice(label=course["title"], amount=course["price"] * 100)]
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=course["title"],
        description=course["desc"],
        payload=str(course["id"]),
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=price,
    )

# === MAIN ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())





