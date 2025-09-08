import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from dotenv import load_dotenv
from db import init_db, get_courses, get_course
from texts import START_TEXT, HELP_TEXT, get_comment, get_ai_recommendation

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")
CURRENCY = os.getenv("CURRENCY", "RUB")

bot = Bot(token=BOT_TOKEN, parse_mode="Markdown")
dp = Dispatcher()

# ===== Главное меню =====
main_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="📚 Покажи свои артефакты")],
        [types.KeyboardButton(text="ℹ️ Объясни, как ты работаешь")]
    ],
    resize_keyboard=True
)

# ===== /start =====
@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer(START_TEXT, reply_markup=main_kb)

# ===== Показ списка курсов =====
@dp.message(F.text == "📚 Покажи свои артефакты")
async def show_courses(message: Message):
    courses = await get_courses()
    if not courses:
        await message.answer("😏 Курсов пока нет. Даже ИИ отдыхает.")
        return

    for course in courses:
        course_id = course[0]
        title = course[1]
        price = course[3]

        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=f"ℹ️ Подробнее", callback_data=f"details:{course_id}")]
            ]
        )

        await message.answer(f"🔥 *{title}* — {price} ₽", reply_markup=kb)

# ===== Карточка курса "Подробнее" =====
@dp.callback_query(F.data.startswith("details:"))
async def course_details(callback: CallbackQuery):
    course_id = int(callback.data.split(":")[1])
    course = await get_course(course_id)

    if not course:
        await callback.message.answer("Курс не найден.")
        return

    title, description, price, link = course[1], course[2], course[3], course[4]

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=f"✅ Оплатить {price} ₽", callback_data=f"buy:{course_id}")]
        ]
    )

    ai_comment = get_ai_recommendation()  # Рандомная рекомендация ИИ

    await callback.message.answer(
        f"🔥 *{title}*\n\n{description}\n\n💰 Цена: {price} ₽\n\n🤖 {ai_comment}",
        reply_markup=kb
    )


# ===== Оплата курса =====
@dp.callback_query(F.data.startswith("buy:"))
async def buy_course(callback: CallbackQuery):
    course_id = int(callback.data.split(":")[1])
    course = await get_course(course_id)

    if not course:
        await callback.message.answer("Курс не найден.")
        return

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course[1],
        description=course[2],
        payload=str(course_id),
        provider_token=PROVIDER_TOKEN,
        currency=CURRENCY,
        prices=[LabeledPrice(label=course[1], amount=course[3]*100)]
    )

# ===== PreCheckout =====
@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# ===== Успешная оплата =====
@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    course_id = int(message.successful_payment.invoice_payload)
    course = await get_course(course_id)
    if course:
        await message.answer(
            f"✅ Оплата прошла. Вот твой доступ:\n{course[4]}\n\n_{get_comment('payment_success')}_"
        )

# ===== Помощь =====
@dp.message(F.text == "ℹ️ Объясни, как ты работаешь")
async def help_text(message: Message):
    await message.answer(HELP_TEXT)

# ===== Старт бота =====
async def main():
    await init_db()
    print("Бот запущен в режиме polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
