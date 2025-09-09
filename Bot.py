# Bot.py — главный файл
import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery

import db
from texts import START_TEXT, CATEGORY_TEXT, PAYMENT_TEXT, SUCCESS_TEXT, ADMIN_HELP, get_recommendation
from keyboards import main_kb, categories_inline, courses_inline, course_details_keyboard

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN", "")
CURRENCY = os.getenv("CURRENCY", "RUB")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, parse_mode="Markdown")
dp = Dispatcher()

# -------------------- старт / помощь --------------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await db.init_db()  # убедиться что база есть
    await message.answer(START_TEXT, reply_markup=main_kb)

@dp.message(F.text == "ℹ️ Как работает наставник ИИ")
async def how_it_works(message: Message):
    await message.answer(CATEGORY_TEXT + "\n" + get_recommendation())

# -------------------- категории --------------------
@dp.message(F.text == "📚 Курсы по категориям")
async def show_categories(message: Message):
    cats = await db.list_categories(active_only=True)
    if not cats:
        await message.answer("Пока нет активных категорий. Админ должен добавить их.")
        return
    kb = categories_inline(cats)
    await message.answer("Выбери категорию:", reply_markup=kb)

@dp.callback_query(F.data.startswith("cat:"))
async def on_cat(callback: CallbackQuery):
    _, cid = callback.data.split(":")
    cid = int(cid)
    courses = await db.list_courses_by_category(cid, active_only=True)
    if not courses:
        await callback.message.answer("В этой категории пока нет активных курсов.")
        return
    kb = courses_inline(courses)
    await callback.message.answer("Курсы в категории:", reply_markup=kb)

# -------------------- карточка курса (подробнее) --------------------
@dp.callback_query(F.data.startswith("details:"))
async def on_details(callback: CallbackQuery):
    _, course_id = callback.data.split(":")
    course_id = int(course_id)
    row = await db.get_course(course_id)
    if not row:
        await callback.message.answer("Курс не найден.")
        return
    cid, category_id, title, description, price, link, is_active = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
    ai_comment = get_recommendation()
    text = f"📌 *{title}*\n\n💰 Цена: *{price}₽*\n\n{description}\n\n🤖 {ai_comment}"
    kb = course_details_keyboard(course_id, price)
    await callback.message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    cats = await db.list_categories(active_only=True)
    kb = categories_inline(cats)
    await callback.message.answer("Категории:", reply_markup=kb)

# -------------------- оплата (через Telegram Payments если PROVIDER_TOKEN задан) --------------------
@dp.callback_query(F.data.startswith("buy:"))
async def on_buy(callback: CallbackQuery):
    if not PROVIDER_TOKEN:
        await callback.message.answer("Платёжный провайдер не настроен. Обратись к админu.")
        return
    _, course_id = callback.data.split(":")
    course_id = int(course_id)
    row = await db.get_course(course_id)
    if not row:
        await callback.message.answer("Курс не найден.")
        return
    title = row[2]
    price = row[4]  # в рублях
    # Telegram Payments ожидает сумму в "minor units" (копейки)
    amount = int(price) * 100
    prices = [LabeledPrice(label=title, amount=amount)]
    await bot.send_invoice(chat_id=callback.from_user.id,
                           title=title,
                           description=row[3][:255],
                           payload=str(course_id),
                           provider_token=PROVIDER_TOKEN,
                           currency=CURRENCY,
                           prices=prices)
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    course_id = int(payment.invoice_payload)
    # Сохраняем покупку
    await db.add_purchase(user_id=message.from_user.id,
                          course_id=course_id,
                          amount=payment.total_amount,
                          currency=payment.currency,
                          telegram_charge_id=payment.telegram_payment_charge_id,
                          provider_charge_id=payment.provider_payment_charge_id)
    row = await db.get_course(course_id)
    if row:
        link = row[5]
        await message.answer(SUCCESS_TEXT.format(link=link))
    else:
        await message.answer("Оплата принята, но курс не найден. Напиши администратору.")

# -------------------- АДМИН: управление категориями и курсами (по ADMIN_ID) --------------------
# простые команды — через /commands или через текст

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return
    await message.answer(ADMIN_HELP)

@dp.message(Command("add_category"))
async def add_category_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    # /add_category Название категории
    parts = message.get_args()
    if not parts:
        await message.answer("Использование: /add_category Название категории")
        return
    name = parts.strip()
    await db.add_category(name)
    await message.answer(f"Категория '{name}' добавлена.")

@dp.message(Command("del_category"))
async def del_category_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.get_args().strip()
    if not args.isdigit():
        await message.answer("Использование: /del_category ID")
        return
    cid = int(args)
    await db.delete_category(cid)
    await message.answer(f"Категория {cid} удалена (и все связанные курсы).")

@dp.message(Command("toggle_category"))
async def toggle_category_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.get_args().strip()
    if not args.isdigit():
        await message.answer("Использование: /toggle_category ID")
        return
    cid = int(args)
    ok = await db.toggle_category(cid)
    await message.answer("Переключено." if ok else "Категория не найдена.")

@dp.message(Command("list_categories"))
async def list_categories_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    cats = await db.list_categories(active_only=False)
    if not cats:
        await message.answer("Категорий нет.")
        return
    lines = []
    for c in cats:
        lines.append(f"{c[0]} — {c[1]} {'(активна)' if c[2] else '(скрыта)'}")
    await message.answer("Категории:\n" + "\n".join(lines))

# --- курсы ---
@dp.message(Command("add_course"))
async def add_course_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    # формат: /add_course <category_id>|<Название>|<Описание>|<Цена>|<Ссылка>
    text = message.get_args()
    if not text or '|' not in text:
        await message.answer("Использование: /add_course <category_id>|<Название>|<Описание>|<Цена>|<Ссылка>")
        return
    try:
        parts = [p.strip() for p in text.split("|")]
        category_id = int(parts[0])
        title = parts[1]
        description = parts[2]
        price = int(parts[3])
        link = parts[4]
        await db.add_course(category_id, title, description, price, link)
        await message.answer(f"Курс '{title}' добавлен в категорию {category_id}.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(Command("del_course"))
async def del_course_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.get_args().strip()
    if not args.isdigit():
        await message.answer("Использование: /del_course ID")
        return
    cid = int(args)
    await db.delete_course(cid)
    await message.answer(f"Курс {cid} удалён.")

@dp.message(Command("list_courses"))
async def list_courses_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.get_args().strip()
    if not args.isdigit():
        await message.answer("Использование: /list_courses <category_id>")
        return
    cat_id = int(args)
    courses = await db.list_courses_by_category(cat_id, active_only=False)
    if not courses:
        await message.answer("Курсов нет.")
        return
    lines = []
    for c in courses:
        lines.append(f"{c[0]} — {c[1]} — {c[3]}₽ {'(активен)' if c[5] else '(скрыт)'}")
    await message.answer("Курсы:\n" + "\n".join(lines))

# -------------------- запуск --------------------
async def main():
    await db.init_db()
    print("Бот запущен (polling)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
