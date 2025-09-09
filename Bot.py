import os, random, asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, CallbackQuery
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import db, keyboards as kb, texts, states

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
CURRENCY = os.getenv("CURRENCY", "RUB")

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

asyncio.run(db.init_db())

# --- Старт ---
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(texts.START_TEXT, reply_markup=kb.main_menu_kb())

# --- Главное меню ---
@dp.message(F.text == "◀️ В главное меню")
@dp.message(F.text == "❌ Отмена")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=kb.main_menu_kb())

# --- Курсы ---
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    categories = await db.list_categories()
    await message.answer("Выберите категорию:", reply_markup=kb.category_kb(categories))

@dp.callback_query(lambda c: c.data.startswith("user_cat:"))
async def choose_category_user(cb: CallbackQuery, state: FSMContext):
    cat_id = int(cb.data.split(":")[1])
    courses = await db.list_courses_by_category(cat_id)
    if not courses:
        await cb.message.answer("Курсы в этой категории отсутствуют", reply_markup=kb.course_kb([]))
        return
    await cb.message.answer("Выберите курс:", reply_markup=kb.course_kb(courses))

@dp.callback_query(lambda c: c.data.startswith("course:"))
async def course_details(cb: CallbackQuery):
    course_id = int(cb.data.split(":")[1])
    course = await db.get_course(course_id)
    if not course:
        await cb.message.answer("Курс не найден")
        return
    ai_comment = random.choice(texts.AI_RECOMMENDATION)
    text = f"<b>{course[2]}</b>\n{course[3]}\n💰 Цена: {course[4]} ₽\n\n{ai_comment}"
    await cb.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb.pay_kb(course_id))

# --- Оплата ---
@dp.callback_query(lambda c: c.data.startswith("pay:"))
async def pay_course(cb: CallbackQuery):
    course_id = int(cb.data.split(":")[1])
    course = await db.get_course(course_id)
    if not course:
        await cb.message.answer("Ошибка: курс не найден")
        return
    prices = [LabeledPrice(label=course[2], amount=int(course[4])*100)]
    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title=course[2],
        description=course[3],
        provider_token=PROVIDER_TOKEN,
        currency=CURRENCY,
        prices=prices,
        payload=str(course_id)
    )

@dp.pre_checkout_query()
async def checkout(pre_checkout: PreCheckoutQuery):
    await pre_checkout.answer(ok=True)

@dp.message(F.content_type == "successful_payment")
async def got_payment(message: Message):
    course_id = int(message.successful_payment.invoice_payload)
    await db.add_purchase(
        user_id=message.from_user.id,
        course_id=course_id,
        amount=message.successful_payment.total_amount//100,
        currency=message.successful_payment.currency,
        telegram_charge_id=message.successful_payment.telegram_payment_charge_id,
        provider_charge_id=message.successful_payment.provider_payment_charge_id
    )
    course = await db.get_course(course_id)
    await message.answer(f"✅ Оплата принята! Ссылка на курс: {course[5]}")

# --- Рекомендации ИИ ---
@dp.message(F.text == "💡 Рекомендации ИИ")
async def ai_recommendation(message: Message):
    await message.answer(random.choice(texts.AI_RECOMMENDATION))

# --- Админка ---
@dp.message(F.text == "🛠️ Админ-панель")
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещен")
        return
    await message.answer(texts.ADMIN_TEXT, reply_markup=kb.admin_kb())
    await state.clear()

# --- Управление категориями ---
@dp.message(F.text == "📂 Управление категориями")
async def manage_categories(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    categories = await db.list_categories(active_only=False)
    await message.answer("Управление категориями:", reply_markup=kb.manage_categories_kb(categories))

@dp.callback_query(lambda c: c.data.startswith("toggle_cat:"))
async def toggle_category(cb: CallbackQuery):
    await db.toggle_category(int(cb.data.split(":")[1]))
    categories = await db.list_categories(active_only=False)
    await cb.message.edit_text("Управление категориями:", reply_markup=kb.manage_categories_kb(categories))

@dp.message(F.text == "➕ Добавить категорию")
async def add_category_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите название новой категории:", reply_markup=kb.cancel_kb())
    await state.set_state(states.AdminStates.add_category)

@dp.message(states.AdminStates.add_category)
async def add_category_save(message: Message, state: FSMContext):
    await db.add_category(message.text)
    await message.answer("Категория добавлена ✅", reply_markup=kb.admin_kb())
    await state.clear()

# --- Управление курсами и добавление курса с кнопкой выхода ---
@dp.message(F.text == "📚 Управление курсами")
async def manage_courses(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    courses = await db.list_courses_by_category(0, active_only=False)
    await message.answer("Управление курсами:", reply_markup=kb.manage_courses_kb(courses))

@dp.message(F.text == "➕ Добавить курс")
async def start_add_course(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    categories = await db.list_categories()
    if not categories:
        await message.answer("Сначала добавьте категорию")
        return
    await message.answer("Выберите категорию для нового курса:", reply_markup=kb.category_kb(categories))
    await state.set_state(states.AdminStates.add_course_category)

# --- FSM обработчики ввода курса --- (с кнопкой выхода)
@dp.callback_query(lambda c: c.data.startswith("user_cat:"))
async def set_course_category(cb: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != states.AdminStates.add_course_category:
        return
    cat_id = int(cb.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await cb.message.answer("Введите название курса:", reply_markup=kb.cancel_kb())
    await state.set_state(states.AdminStates.add_course_title)

# Остальные состояния add_course_title, add_course_description, add_course_price, add_course_link
# Обрабатываются аналогично с использованием kb.cancel_kb() для отмены

# --- Запуск Polling ---
if __name__ == "__main__":
    print("Бот запущен на polling...")
    asyncio.run(dp.start_polling(bot))



