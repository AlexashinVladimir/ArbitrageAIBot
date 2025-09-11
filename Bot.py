# Bot.py
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
from states import AddCategory, AddCourse, EditCategory, EditCourse

# config
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "") or os.getenv("PAYMENTS_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set in .env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# helper
def extract_int(s: str):
    if not s:
        return None
    m = re.search(r"(\d+)(?!.*\d)", s)
    return int(m.group(1)) if m else None

def is_admin(user_id: int):
    return user_id == ADMIN_ID

# start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # ensure tables
    await db.create_tables()
    admin = is_admin(message.from_user.id)
    await message.answer(
        "👋 Я — циничный ИИ с глубокой философией. Помогу стать лучше — если хватит смелости.",
        reply_markup=kb.main_menu(admin)
    )

# about
@dp.message(F.text == "ℹ️ О боте")
async def about(message: Message):
    await message.answer("Я не даю пустых обещаний. Дам тебе инструменты и немного жесткой правды.")

# show categories
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    cats = await db.get_categories()
    if not cats:
        await message.answer("Категорий пока нет.")
        return
    await message.answer("Выбирай категорию:", reply_markup=kb.categories_inline(cats))

# category -> show courses
@dp.callback_query(F.data.startswith("category:"))
async def category_cb(callback: CallbackQuery):
    await callback.answer()
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка категории.")
        return
    courses = await db.get_courses(cid)
    if not courses:
        await callback.message.answer("В этой категории пока нет курсов.")
        return
    for course in courses:
        text = f"<b>{course['title']}</b>\n\n{course['description']}"
        await callback.message.answer(text, reply_markup=kb.courses_inline([course]))

# buy
@dp.callback_query(F.data.startswith("buy:"))
async def buy_cb(callback: CallbackQuery):
    await callback.answer()
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
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
        await callback.message.answer("Платежи не настроены.")
        return
    prices = [LabeledPrice(label=course["title"], amount=price * 100)]
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=course["title"],
            description=(course.get("description") or "")[:1000],
            payload=f"course:{cid}",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter=f"buy_{cid}"
        )
    except Exception:
        logger.exception("send_invoice failed")
        await callback.message.answer("Ошибка отправки инвойса.")
    return

@dp.pre_checkout_query()
async def precheckout(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload or ""
    cid = extract_int(payload)
    if cid is None:
        await message.answer("Оплата принята, но не удалось определить курс.")
        return
    course = await db.get_course(cid)
    if not course:
        await message.answer("Оплата принята, но курс не найден.")
        return
    link = course.get("link") or ""
    if link:
        await message.answer(f"✅ Оплата прошла успешно!\n\nВот ссылка: {link}")
    else:
        await message.answer("Оплата прошла успешно — ссылка не найдена. Свяжитесь с админом.")

# admin panel
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Панель администратора:", reply_markup=kb.admin_menu())

# add category (admin)
@dp.message(F.text == "➕ Добавить категорию")
async def start_add_category(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddCategory.waiting_for_title)
    await message.answer("Введи название новой категории (или ❌ Отмена):", reply_markup=kb.cancel_kb())

@dp.message(StateFilter(AddCategory.waiting_for_title))
async def finish_add_category(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена ✅", reply_markup=kb.admin_menu())

# manage categories
@dp.message(F.text == "📂 Управление категориями")
async def manage_categories(message: Message):
    if not is_admin(message.from_user.id):
        return
    cats = await db.get_categories()
    if not cats:
        await message.answer("Категорий нет.")
        return
    await message.answer("Категории:", reply_markup=kb.edit_delete_inline("category", cats))

@dp.callback_query(F.data.startswith("delete_category:"))
async def delete_category(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    await db.delete_category(cid)
    await callback.message.answer("Категория удалена.")

@dp.callback_query(F.data.startswith("edit_category:"))
async def edit_category_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    await state.update_data(edit_cat_id=cid)
    await state.set_state(EditCategory.waiting_for_new_title)
    await callback.message.answer("Введи новое название категории (или ❌ Отмена):", reply_markup=kb.cancel_kb())

@dp.message(StateFilter(EditCategory.waiting_for_new_title))
async def edit_category_finish(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
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

# add course (admin) - full FSM
@dp.message(F.text == "➕ Добавить курс")
async def start_add_course(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    cats = await db.get_categories()
    if not cats:
        await message.answer("Сначала добавь категорию.", reply_markup=kb.admin_menu())
        return
    # choose category inline
    await state.set_state(AddCourse.choosing_category)
    await message.answer("Выбери категорию для нового курса:", reply_markup=kb.categories_inline(cats))

@dp.callback_query(StateFilter(AddCourse.choosing_category))
async def choose_category_for_course(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка выбора категории.")
        return
    await state.update_data(category_id=cid)
    await state.set_state(AddCourse.waiting_for_title)
    await callback.message.answer("Введите название курса (или ❌ Отмена):", reply_markup=kb.cancel_kb())

@dp.message(StateFilter(AddCourse.waiting_for_title))
async def add_course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Введите описание курса (или ❌ Отмена):", reply_markup=kb.cancel_kb())

@dp.message(StateFilter(AddCourse.waiting_for_description))
async def add_course_description(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Введите цену в рублях (целое число) (или ❌ Отмена):", reply_markup=kb.cancel_kb())

@dp.message(StateFilter(AddCourse.waiting_for_price))
async def add_course_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    if not message.text.isdigit():
        await message.answer("Цена должна быть числом. Попробуйте снова.")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Вставьте ссылку на курс (или ❌ Отмена):", reply_markup=kb.cancel_kb())

@dp.message(StateFilter(AddCourse.waiting_for_link))
async def add_course_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
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
    await message.answer("Курс добавлен ✅", reply_markup=kb.admin_menu())

# manage courses (list + edit/delete)
@dp.message(F.text == "📘 Управление курсами")
async def manage_courses(message: Message):
    if not is_admin(message.from_user.id):
        return
    cats = await db.get_categories()
    courses_all = []
    for c in cats:
        cs = await db.get_courses(c["id"])
        for cr in cs:
            courses_all.append(cr)
    if not courses_all:
        await message.answer("Курсов нет.")
        return
    await message.answer("Курсы:", reply_markup=kb.edit_delete_inline("course", courses_all))

@dp.callback_query(F.data.startswith("delete_course:"))
async def delete_course_cb(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    await db.delete_course(cid)
    await callback.message.answer("Курс удалён.")

@dp.callback_query(F.data.startswith("edit_course:"))
async def edit_course_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    # ask which field
    await state.update_data(edit_course_id=cid)
    await state.set_state(EditCourse.waiting_for_field_choice)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data=f"edit_course_field:title:{cid}")],
        [InlineKeyboardButton(text="Описание", callback_data=f"edit_course_field:description:{cid}")],
        [InlineKeyboardButton(text="Цена", callback_data=f"edit_course_field:price:{cid}")],
        [InlineKeyboardButton(text="Ссылка", callback_data=f"edit_course_field:link:{cid}")]
    ])
    await callback.message.answer("Что редактируем?", reply_markup=markup)

@dp.callback_query(F.data.regexp(r"^edit_course_field:(title|description|price|link):\d+$"))
async def edit_course_field_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    field = parts[1]
    cid = int(parts[2])
    await state.update_data(edit_course_id=cid, edit_field=field)
    await state.set_state(EditCourse.waiting_for_new_value)
    await callback.message.answer(f"Введи новое значение для {field} (или ❌ Отмена):", reply_markup=kb.cancel_kb())

@dp.message(StateFilter(EditCourse.waiting_for_new_value))
async def edit_course_save(message: Message, state: FSMContext):
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
    if field == "price" and not message.text.isdigit():
        await message.answer("Цена должна быть числом.")
        return
    value = int(message.text) if field == "price" else message.text
    # try update_course_field otherwise full update
    if hasattr(db, "update_course_field"):
        await db.update_course_field(cid, field, value)
    else:
        # fallback: fetch course then call update_course with replaced field
        cur = await db.get_course(cid)
        if not cur:
            await message.answer("Курс не найден.")
            await state.clear()
            return
        title = cur.get("title")
        description = cur.get("description")
        price = cur.get("price")
        link = cur.get("link")
        if field == "title":
            title = value
        elif field == "description":
            description = value
        elif field == "price":
            price = value
        elif field == "link":
            link = value
        await db.update_course(cid, title, description, price, link)
    await state.clear()
    await message.answer("Курс обновлён ✅", reply_markup=kb.admin_menu())

# cancel handler
@dp.message(F.text == "❌ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    if is_admin(message.from_user.id):
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
    else:
        await message.answer("Отменено.", reply_markup=kb.main_menu(False))

# catch-all callback to avoid 'not handled' logs and to debug unexpected callback_data
@dp.callback_query()
async def debug_callback(cb: CallbackQuery):
    logger.debug("Unhandled callback data: %s from %s", cb.data, cb.from_user.id)
    await cb.answer()

# run
async def main():
    await db.create_tables()
    logger.info("Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

