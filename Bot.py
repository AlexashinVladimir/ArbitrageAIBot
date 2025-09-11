import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums import ParseMode

import keyboards as kb
import db


logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "ТОКЕН_ТВОЕГО_БОТА"
PAYMENT_PROVIDER_TOKEN = "381764678:TEST:1122334455667788"  # тестовый ЮKassa

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


# --- FSM для добавления категорий и курсов ---
class AddCategory(StatesGroup):
    waiting_for_title = State()


class AddCourse(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_link = State()
    waiting_for_category = State()


# --- Старт ---
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    is_admin = message.from_user.id in [123456789]  # впиши свой Telegram ID
    await message.answer(
        "Добро пожаловать. Да, я бот, и у меня циничная философия. Но если ты тут — значит ищешь рост.",
        reply_markup=kb.main_menu(admin=is_admin)
    )


# --- Пользовательские ---
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    categories = await db.get_categories()
    if not categories:
        return await message.answer("Категорий пока нет.")
    await message.answer("Выбирай категорию:", reply_markup=kb.categories_keyboard(categories))


@dp.callback_query(F.data.startswith("category:"))
async def show_courses(cb: CallbackQuery):
    cat_id = int(cb.data.split(":")[1])
    courses = await db.get_courses(cat_id)
    if not courses:
        return await cb.message.edit_text("Курсов пока нет.")
    await cb.message.edit_text("Вот что у меня есть:", reply_markup=kb.courses_keyboard(courses))


@dp.callback_query(F.data.startswith("course:"))
async def course_details(cb: CallbackQuery):
    course_id = int(cb.data.split(":")[1])
    course = await db.get_course(course_id)
    if not course:
        return await cb.answer("Курс не найден", show_alert=True)
    text = f"<b>{course['title']}</b>\n\n{course['description']}\n\nЦена: {course['price']}₽"
    await cb.message.edit_text(text, reply_markup=kb.course_actions(course_id))


# --- Оплата ---
@dp.callback_query(F.data.startswith("buy:"))
async def process_buy(cb: CallbackQuery):
    course_id = int(cb.data.split(":")[1])
    course = await db.get_course(course_id)
    if not course:
        return await cb.answer("Курс не найден", show_alert=True)

    prices = [LabeledPrice(label=course["title"], amount=int(course["price"]) * 100)]
    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title=course["title"],
        description=course["description"],
        payload=f"course_{course_id}",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter="purchase-course",
    )
    await cb.answer()


@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message(F.successful_payment)
async def got_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    course_id = int(payload.replace("course_", ""))
    course = await db.get_course(course_id)
    if course:
        await message.answer(f"Оплата прошла успешно! Вот твоя ссылка: {course['link']}")


# --- Админ-панель ---
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id not in [123456789]:
        return await message.answer("Ты не админ.")
    await message.answer("Что будем делать?", reply_markup=kb.admin_panel())


@dp.callback_query(F.data == "admin_add_category")
async def admin_add_category(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Введи название новой категории:")
    await state.set_state(AddCategory.waiting_for_title)
    await cb.answer()


@dp.message(AddCategory.waiting_for_title)
async def save_category(message: Message, state: FSMContext):
    await db.add_category(message.text)
    await message.answer("Категория добавлена!")
    await state.clear()


@dp.callback_query(F.data == "admin_add_course")
async def admin_add_course(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Введи название курса:")
    await state.set_state(AddCourse.waiting_for_title)
    await cb.answer()


@dp.message(AddCourse.waiting_for_title)
async def course_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Теперь введи описание курса:")


@dp.message(AddCourse.waiting_for_description)
async def course_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Укажи цену в рублях:")


@dp.message(AddCourse.waiting_for_price)
async def course_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Цена должна быть числом.")
    await state.update_data(price=int(message.text))
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Введи ссылку на курс:")


@dp.message(AddCourse.waiting_for_link)
async def course_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text)
    categories = await db.get_categories()
    if not categories:
        return await message.answer("Нет категорий. Сначала создай категорию.")
    text = "Выбери категорию:"
    buttons = [
        [InlineKeyboardButton(text=c["title"], callback_data=f"set_course_category:{c['id']}")]
        for c in categories
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await state.set_state(AddCourse.waiting_for_category)
    await message.answer(text, reply_markup=markup)


@dp.callback_query(F.data.startswith("set_course_category:"))
async def course_set_category(cb: CallbackQuery, state: FSMContext):
    cat_id = int(cb.data.split(":")[1])
    data = await state.get_data()
    await db.add_course(
        title=data["title"],
        description=data["description"],
        price=data["price"],
        link=data["link"],
        category_id=cat_id,
    )
    await state.clear()
    await cb.message.answer("Курс добавлен!")
    await cb.answer()


# --- Debug handler ---
@dp.callback_query()
async def debug_callback(cb: CallbackQuery):
    print("DEBUG CALLBACK DATA:", cb.data)
    await cb.answer()


# --- Run bot ---
async def main():
    await db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

