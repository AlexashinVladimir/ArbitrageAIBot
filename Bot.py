import asyncio
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from dotenv import load_dotenv

import db

# === Загружаем переменные окружения ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "381764678:TEST:12345")  # тестовый токен по умолчанию

# === Инициализация бота ===
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# === Состояния для FSM ===
class AddCategory(StatesGroup):
    waiting_for_name = State()


class AddCourse(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_link = State()
    waiting_for_category = State()


# === Клавиатуры ===
def main_menu(is_admin: bool = False):
    kb = ReplyKeyboardBuilder()
    kb.button(text="📚 Курсы")
    kb.button(text="ℹ️ О боте")
    if is_admin:
        kb.button(text="⚙️ Админ панель")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


def categories_kb(categories):
    kb = InlineKeyboardBuilder()
    for c in categories:
        kb.button(text=c["name"], callback_data=f"category_{c['id']}")
    kb.adjust(1)
    return kb.as_markup()


def courses_kb(courses):
    kb = InlineKeyboardBuilder()
    for c in courses:
        kb.button(text=f"💰 Купить: {c['price']} ₽", callback_data=f"buy_{c['id']}")
    kb.adjust(1)
    return kb.as_markup()


def admin_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="➕ Добавить категорию")
    kb.button(text="➕ Добавить курс")
    kb.button(text="❌ Отмена")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


# === Хендлеры ===
@dp.message(Command("start"))
async def cmd_start(message: Message):
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(
        "Привет 👋\nЯ циничный бот, который продаёт курсы. "
        "Выбирай, учись и становись лучше.",
        reply_markup=main_menu(is_admin)
    )


@dp.message(F.text == "ℹ️ О боте")
async def about(message: Message):
    await message.answer("🤖 Я бот-киоск. Я не даю обещаний, только курсы и голую правду.")


@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        await message.answer("Пока нет категорий.")
        return
    await message.answer("Выбери категорию:", reply_markup=categories_kb(categories))


@dp.callback_query(F.data.startswith("category_"))
async def show_courses(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    courses = await db.get_courses(category_id)
    if not courses:
        await callback.message.answer("В этой категории пока нет курсов.")
        return
    for c in courses:
        text = f"<b>{c['title']}</b>\n\n{c['description']}"
        await callback.message.answer(text, reply_markup=courses_kb([c]))


@dp.callback_query(F.data.startswith("buy_"))
async def buy_course(callback: CallbackQuery):
    course_id = int(callback.data.split("_")[1])
    courses = await db.get_courses(category_id=1)  # упрощённо (можно доработать)
    course = next((c for c in courses if c["id"] == course_id), None)
    if not course:
        await callback.answer("Курс не найден", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course["title"],
        description=course["description"],
        payload=str(course["id"]),
        provider_token=PAYMENT_PROVIDER,
        currency="RUB",
        prices=[LabeledPrice(label=course["title"], amount=course["price"] * 100)]
    )


@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)


@dp.message(F.content_type == "successful_payment")
async def process_successful_payment(message: Message):
    course_id = int(message.successful_payment.invoice_payload)
    courses = await db.get_courses(category_id=1)  # временно
    course = next((c for c in courses if c["id"] == course_id), None)
    if course:
        await message.answer(f"✅ Оплата прошла!\nВот доступ к курсу: {course['link']}")


# === Админ панель ===
@dp.message(F.text == "⚙️ Админ панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Добро пожаловать в админку:", reply_markup=admin_menu())


# === Добавление категории ===
@dp.message(F.text == "➕ Добавить категорию")
async def admin_add_category(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите название новой категории:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AddCategory.waiting_for_name)


@dp.message(AddCategory.waiting_for_name)
async def save_category(message: Message, state: FSMContext):
    await db.add_category(message.text)
    await message.answer("Категория добавлена ✅", reply_markup=main_menu(True))
    await state.clear()


# === Добавление курса ===
@dp.message(F.text == "➕ Добавить курс")
async def admin_add_course(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите название курса:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AddCourse.waiting_for_title)


@dp.message(AddCourse.waiting_for_title)
async def course_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введите описание курса:")
    await state.set_state(AddCourse.waiting_for_description)


@dp.message(AddCourse.waiting_for_description)
async def course_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите цену курса (в рублях):")
    await state.set_state(AddCourse.waiting_for_price)


@dp.message(AddCourse.waiting_for_price)
async def course_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число (цену в рублях):")
        return
    await state.update_data(price=int(message.text))
    await message.answer("Введите ссылку на курс:")
    await state.set_state(AddCourse.waiting_for_link)


@dp.message(AddCourse.waiting_for_link)
async def course_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    categories = await db.get_categories()
    kb = InlineKeyboardBuilder()
    for c in categories:
        kb.button(text=c["name"], callback_data=f"coursecat_{c['id']}")
    kb.adjust(1)
    await message.answer("Выберите категорию для курса:", reply_markup=kb.as_markup())
    await state.set_state(AddCourse.waiting_for_category)


@dp.callback_query(F.data.startswith("coursecat_"))
async def course_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    await db.add_course(
        data["title"], data["description"], data["price"], data["link"], category_id
    )
    await callback.message.answer("Курс добавлен ✅", reply_markup=main_menu(True))
    await state.clear()


# === Отмена ===
@dp.message(F.text == "❌ Отмена")
async def cancel_any(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🚫 Действие отменено.", reply_markup=main_menu(message.from_user.id == ADMIN_ID))


# === MAIN ===
async def main():
    await db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


