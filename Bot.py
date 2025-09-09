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

# Главное меню и отмена
@dp.message(F.text.in_(["◀️ В главное меню", "❌ Отмена"]))
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=kb.main_menu_kb())

# Курсы
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    categories = await db.list_categories()
    await message.answer("Выберите категорию:", reply_markup=kb.category_kb(categories))

@dp.callback_query(lambda c: c.data.startswith("user_cat:"))
async def choose_category_user(cb: CallbackQuery):
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

# Оплата
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

# Рекомендации ИИ
@dp.message(F.text == "💡 Рекомендации ИИ")
async def ai_recommendation(message: Message):
    await message.answer(random.choice(texts.AI_RECOMMENDATION))

# Админ-панель
@dp.message(F.text == "🛠️ Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещен")
        return
    await message.answer(texts.ADMIN_TEXT, reply_markup=kb.admin_kb())

# Управление категориями и курсами, добавление, с кнопкой отмены
# ... (аналогично FSM, как мы делали раньше, с kb.cancel_kb() на каждом шаге)
# Для краткости в этом примере полный FSM добавления категорий и курсов добавляем отдельно.

# Запуск polling
if __name__ == "__main__":
    print("Бот запущен на polling...")
    asyncio.run(dp.start_polling(bot))




