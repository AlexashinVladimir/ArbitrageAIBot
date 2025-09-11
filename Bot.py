# Bot.py — full bot (Aiogram 3.6)
import asyncio
import logging
import os
import re
from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton

import db
import keyboards as kb
import states as st

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")  # provider token or empty
DB_PATH = os.getenv("DB_PATH", "database.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# Helpers
def extract_int(s: str | None) -> int | None:
    if not s:
        return None
    m = re.search(r"(\d+)(?!.*\d)", s)
    return int(m.group(1)) if m else None


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def safe_kb(name: str, *args, default=None):
    fn = getattr(kb, name, None)
    if callable(fn):
        try:
            return fn(*args)
        except Exception as e:
            logger.exception("keyboard %s failed: %s", name, e)
    return default


# ---------------- Start ----------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # ensure DB
    try:
        await db.create_tables()
    except Exception:
        logger.exception("create_tables failed")
    admin_flag = is_admin(message.from_user.id)
    main = safe_kb("main_menu", admin_flag)
    if main is None:
        buttons = [[types.KeyboardButton(text="📚 Курсы")], [types.KeyboardButton(text="ℹ️ О боте")]]
        if admin_flag:
            buttons.append([types.KeyboardButton(text="⚙️ Админ-панель")])
        main = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("Я — циничный ИИ, помогающий прокачиваться. Выбирай.", reply_markup=main)


# ---------------- About ----------------
@dp.message(F.text == "ℹ️ О боте")
async def about_handler(message: Message):
    await message.answer("Немного цинизма, немного практики — и ты становишься лучше.")


# ---------------- User: categories -> courses -> buy ----------------
@dp.message(F.text == "📚 Курсы")
async def user_show_categories(message: Message):
    cats = await db.get_categories()
    if not cats:
        await message.answer("Категорий пока нет.")
        return
    markup = safe_kb("categories_inline", cats, False) or kb.categories_inline(cats, False)
    await message.answer("Выбирай категорию:", reply_markup=markup)


@dp.callback_query(F.data.startswith("catview:"))
async def user_show_courses(callback: CallbackQuery):
    await callback.answer()
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить категорию.")
        return
    courses = await db.get_courses_by_category(cid)
    if not courses:
        await callback.message.answer("В этой категории пока нет курсов.")
        return
    for c in courses:
        text = f"<b>{c['title']}</b>\n\n{c.get('description','')}"
        buy_kb = safe_kb("courses_inline", [c]) or kb.courses_inline([c])
        await callback.message.answer(text, reply_markup=buy_kb)


@dp.callback_query(F.data.startswith("buy:"))
async def user_buy(callback: CallbackQuery):
    await callback.answer()
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка покупки.")
        return
    course = await db.get_course(cid)
    if not course:
        await callback.message.answer("Курс не найден.")
        return
    price = int(course.get("price", 0) or 0)
    if price <= 0:
        await callback.message.answer("Неверная цена.")
        return
    if not PAYMENT_PROVIDER_TOKEN:
        await callback.message.answer("Платежи не настроены. Обратитесь к администратору.")
        return
    prices = [LabeledPrice(label=course.get("title", "Курс"), amount=price * 100)]
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=course.get("title", "Курс"),
            description=(course.get("description") or "")[:1000],
            payload=f"course:{cid}",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter=f"course_{cid}"
        )
    except Exception:
        logger.exception("send_invoice failed")
        await callback.message.answer("Ошибка отправки инвойса.")


@dp.pre_checkout_query()
async def precheckout(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    try:
        payload = message.successful_payment.invoice_payload or ""
        cid = extract_int(payload)
        if cid is None:
            await message.answer("Оплата принята, но не найден курс.")
            return
        course = await db.get_course(cid)
        if not course:
            await message.answer("Оплата принята, но курс не найден.")
            return
        link = course.get("link") or ""
        if link:
            await message.answer(f"✅ Оплата прошла успешно! Вот ссылка на курс:\n{link}")
        else:
            await message.answer("✅ Оплата прошла успешно. Ссылка отсутствует — свяжитесь с админом.")
    except Exception:
        logger.exception("successful_payment error")
        await message.answer("Оплата принята — произошла ошибка при обработке.")


# ---------------- Admin panel (entry) ----------------
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа.")
        return
    await message.answer("Панель администратора:", reply_markup=kb.admin_menu())


# ---------------- Categories management ----------------
@dp.message(F.text == "➕ Добавить категорию")
async def admin_add_category_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(st.AddCategory.waiting_for_title)
    await message.answer("Введи название новой категории (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(st.AddCategory.waiting_for_title))
async def admin_add_category_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu())
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена ✅", reply_markup=kb.admin_menu())


@dp.message(F.text == "📂 Управление категориями")
async def admin_manage_categories(message: Message):
    if not is_admin(message.from_user.id):
        return
    cats = await db.get_categories()
    if not cats:
        await message.answer("Категорий нет.", reply_markup=kb.admin_menu())
        return
    adapted = [{"id": c["id"], "title": c["title"]} for c in cats]
    inline = safe_kb("edit_delete_inline", "category", adapted) or kb.edit_delete_inline("category", adapted)
    await message.answer("Категории:", reply_markup=inline)


@dp.callback_query(F.data.startswith("delete_category:"))
async def admin_delete_category(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    await db.delete_category(cid)
    await callback.message.answer("Категория удалена.", reply_markup=kb.admin_menu())


@dp.callback_query(F.data.startswith("edit_category:"))
async def admin_edit_category_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    await state.update_data(edit_cat_id=cid)
    await state.set_state(st.EditCategory.waiting_for_new_title)
    await callback.message.answer("Введи новое название категории (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(st.EditCategory.waiting_for_new_title))
async def admin_edit_category_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu())
        return
    data = await state.get_data()
    cid = data.get("edit_cat_id")
    if cid is None:
        await message.answer("Нет категории.")
        await state.clear()
        return
    await db.update_category(cid, message.text)
    await state.clear()
    await message.answer("Категория обновлена ✅", reply_markup=kb.admin_menu())


# ---------------- Courses management: add (with catadd prefix) ----------------
@dp.message(F.text == "➕ Добавить курс")
async def admin_add_course_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    cats = await db.get_categories()
    if not cats:
        await message.answer("Сначала добавь категорию.", reply_markup=kb.admin_menu())
        return
    markup = kb.categories_inline(cats, for_add=True)
    await state.set_state(st.AddCourse.choosing_category)
    await message.answer("Выбери категорию для нового курса:", reply_markup=markup)


@dp.callback_query(StateFilter(st.AddCourse.choosing_category), F.data.startswith("catadd:"))
async def admin_choose_cat_for_course(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить категорию.")
        return
    await state.update_data(category_id=cid)
    await state.set_state(st.AddCourse.waiting_for_title)
    await callback.message.answer("Введите название курса (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(st.AddCourse.waiting_for_title))
async def admin_add_course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu())
        return
    await state.update_data(title=message.text)
    await state.set_state(st.AddCourse.waiting_for_description)
    await message.answer("Введите описание курса (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(st.AddCourse.waiting_for_description))
async def admin_add_course_description(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu())
        return
    await state.update_data(description=message.text)
    await state.set_state(st.AddCourse.waiting_for_price)
    await message.answer("Введите цену в рублях (целое число) (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(st.AddCourse.waiting_for_price))
async def admin_add_course_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu())
        return
    if not message.text.isdigit():
        await message.answer("Цена должна быть числом. Попробуй ещё раз.")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(st.AddCourse.waiting_for_link)
    await message.answer("Вставь ссылку на курс (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(st.AddCourse.waiting_for_link))
async def admin_add_course_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu())
        return
    data = await state.get_data()
    cid = data.get("category_id")
    title = data.get("title")
    description = data.get("description")
    price = data.get("price")
    link = message.text
    if None in (cid, title, description, price):
        await state.clear()
        await message.answer("Недостаточно данных — отменено.", reply_markup=kb.admin_menu())
        return
    await db.add_course(cid, title, description, price, link)
    await state.clear()
    await message.answer("Курс создан ✅", reply_markup=kb.admin_menu())


# ---------------- Manage courses list & quick edit/delete ----------------
@dp.message(F.text == "📘 Управление курсами")
async def admin_manage_courses(message: Message):
    if not is_admin(message.from_user.id):
        return
    courses = await db.get_all_courses()
    if not courses:
        await message.answer("Курсов нет.", reply_markup=kb.admin_menu())
        return
    adapted = [{"id": c["id"], "title": c["title"]} for c in courses]
    inline = safe_kb("edit_delete_inline", "course", adapted) or kb.edit_delete_inline("course", adapted)
    await message.answer("Курсы:", reply_markup=inline)


@dp.callback_query(F.data.startswith("delete_course:"))
async def admin_delete_course(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    await db.delete_course(cid)
    await callback.message.answer("Курс удалён.", reply_markup=kb.admin_menu())


@dp.callback_query(F.data.startswith("edit_course:"))
async def admin_edit_course_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    await state.update_data(edit_course_id=cid)
    await state.set_state(st.EditCourse.waiting_for_field_choice)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data=f"edit_course_field:title:{cid}")],
        [InlineKeyboardButton(text="Описание", callback_data=f"edit_course_field:description:{cid}")],
        [InlineKeyboardButton(text="Цена", callback_data=f"edit_course_field:price:{cid}")],
        [InlineKeyboardButton(text="Ссылка", callback_data=f"edit_course_field:link:{cid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ])
    await callback.message.answer("Что редактируем?", reply_markup=markup)


@dp.callback_query(F.data.regexp(r"^edit_course_field:(title|description|price|link):\d+$"))
async def admin_edit_course_field_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    field = parts[1]
    cid = int(parts[2])
    await state.update_data(edit_course_id=cid, edit_field=field)
    await state.set_state(st.EditCourse.waiting_for_new_value)
    await callback.message.answer(f"Введи новое значение для {field} (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(st.EditCourse.waiting_for_new_value))
async def admin_save_edited_course_field(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    data = await state.get_data()
    cid = data.get("edit_course_id")
    field = data.get("edit_field")
    if cid is None or not field:
        await message.answer("Нет данных для редактирования.")
        await state.clear()
        return
    value = message.text
    if field == "price":
        if not value.isdigit():
            await message.answer("Цена должна быть числом.")
            return
        value = int(value)
    await db.update_course_field(cid, field, value)
    await state.clear()
    await message.answer("Курс обновлён ✅", reply_markup=kb.admin_menu())


# ---------------- Back / Cancel handlers ----------------
@dp.callback_query(F.data == "back_to_admin")
async def back_inline_admin(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Возврат в админ-панель.", reply_markup=kb.admin_menu())


@dp.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    await callback.answer()
    cats = await db.get_categories()
    await callback.message.answer("Категории:", reply_markup=kb.categories_inline(cats, False))


@dp.message(F.text == "⬅️ Назад")
async def back_from_admin(message: Message):
    if is_admin(message.from_user.id):
        await message.answer("Возврат в главное меню.", reply_markup=kb.main_menu(True))
    else:
        await message.answer("Возврат в главное меню.", reply_markup=kb.main_menu(False))


@dp.message(F.text == "❌ Отмена")
async def cancel_any(message: Message, state: FSMContext):
    await state.clear()
    if is_admin(message.from_user.id):
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
    else:
        await message.answer("Отменено.", reply_markup=kb.main_menu(False))


# Catch-all callback to avoid "update not handled"
@dp.callback_query()
async def catch_all(cb: CallbackQuery):
    logger.debug("Unhandled callback data: %s from %s", cb.data, cb.from_user.id)
    await cb.answer()


# Run
async def main():
    try:
        await db.create_tables()
    except Exception:
        logger.exception("DB create_tables failed at startup")
    logger.info("Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


