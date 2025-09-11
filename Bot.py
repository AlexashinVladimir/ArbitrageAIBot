# Bot.py — устойчивый основной файл, Aiogram 3.6
import asyncio
import logging
import os
import re
import traceback

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.types import LabeledPrice, PreCheckoutQuery

# локальные модули (должны быть рядом)
import db
import keyboards as kb
import texts
from states import AddCategory, AddCourse, EditCourse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- конфиг из .env ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
# поддерживаем оба имени переменной на случай, если ты раньше использовал другое
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN") or os.getenv("PAYMENTS_PROVIDER_TOKEN")

if not TOKEN:
    logger.error("BOT_TOKEN не задан в .env — бот не может запуститься.")
    raise RuntimeError("BOT_TOKEN not set")

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- Утилиты для совместимости с разными версиями db/keyboards ---

def extract_id_from_callback(data: str) -> int | None:
    """Вытащить последнее число из callback_data (напр. 'buy:12', 'buy_12', 'edit-12')."""
    if not data:
        return None
    m = re.search(r'(\d+)(?!.*\d)', data)
    if m:
        return int(m.group(1))
    return None

def has_db_fn(*names):
    for n in names:
        if hasattr(db, n):
            return getattr(db, n)
    return None

def has_kb_fn(*names):
    for n in names:
        if hasattr(kb, n):
            return getattr(kb, n)
    return None

# совместимые точки входа для списков/CRUD
db_list_categories = has_db_fn("list_categories", "get_categories", "get_categories_list", "get_categories")
db_list_courses = has_db_fn("list_courses", "get_courses")
db_list_courses_by_category = has_db_fn("list_courses_by_category", "get_courses_by_category", "get_courses_by_cat")
db_get_course = has_db_fn("get_course", "get_course_by_id", "fetch_course")
db_add_category = has_db_fn("add_category", "create_category")
db_add_course = has_db_fn("add_course", "create_course")
db_delete_category = has_db_fn("delete_category", "remove_category")
db_delete_course = has_db_fn("delete_course", "remove_course")
db_update_course_field = has_db_fn("update_course_field", "update_course", "update_course_full")
db_record_purchase = has_db_fn("record_purchase", "add_purchase", "save_purchase")
db_ensure_user = has_db_fn("ensure_user", None)

# клавиатуры (попробуем найти наиболее вероятные имена)
kb_main = has_kb_fn("main_menu", "main_kb", "main")
kb_admin_menu = has_kb_fn("admin_menu", "admin_main_kb", "admin_panel_kb", "admin_menu_kb")
kb_categories_inline = has_kb_fn("categories_inline", "categories_admin_inline", "categories_inline_kb")
kb_categories_admin_inline = has_kb_fn("categories_admin_inline", "categories_admin")
kb_course_inline = has_kb_fn("course_inline", "buy_kb")
kb_admin_courses_inline = has_kb_fn("admin_courses_inline", "admin_courses")
kb_choose_category = has_kb_fn("choose_category_kb", "choose_category", "choose_category_keyboard")
kb_cancel = getattr(kb, "cancel_kb", None) or has_kb_fn("cancel_kb", "cancel_keyboard")
kb_course_admin_inline = has_kb_fn("course_admin_inline", "course_manage_kb", "course_admin")

# Если некоторые функции не найдены — будем строить клавиатуры вручную ниже.

# ---------------- Handlers ----------------

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    try:
        # ensure DB
        await db.init_db()
    except Exception:
        logger.exception("init_db error (ignored)")

    is_admin = message.from_user.id == ADMIN_ID

    # try texts.random_start if exists
    start_text = None
    try:
        start_text = texts.random_start()
    except Exception:
        start_text = "Привет. Выбирай."
    # pick keyboard
    try:
        if kb_main:
            kb_menu = kb_main(is_admin) if callable(kb_main) else kb_main
        else:
            buttons = [[types.KeyboardButton(text="📚 Курсы")], [types.KeyboardButton(text="ℹ️ О боте")]]
            if is_admin:
                buttons.append([types.KeyboardButton(text="👑 Админ-панель")])
            kb_menu = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    except Exception:
        kb_menu = None

    await message.answer(start_text, reply_markup=kb_menu)


# ---------- User: categories -> courses ----------
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: types.Message):
    try:
        cats = await db_list_categories()
    except Exception as e:
        logger.exception("Ошибка при получении категорий")
        await message.answer("Ошибка при получении категорий.")
        return

    if not cats:
        await message.answer(getattr(texts, "CATEGORY_EMPTY", "Категорий пока нет."))
        return

    # try to render categories keyboard from kb
    try:
        if kb_categories := kb_categories_inline := (kb_categories_inline if (kb_categories_inline := kb_categories_inline if False else None) else None):
            pass
    except Exception:
        pass

    # prefer keyboard function if exists
    if kb_categories_inline and callable(kb_categories_inline):
        try:
            kb_markup = kb_categories_inline([dict(c) for c in cats])
            await message.answer("Выберите категорию:", reply_markup=kb_markup)
            return
        except Exception:
            logger.exception("kb.categories_inline failed")

    # fallback: build inline keyboard
    items = []
    for c in cats:
        cid = c["id"] if isinstance(c, dict) else c[0]
        title = c["title"] if isinstance(c, dict) else c[1]
        items.append([types.InlineKeyboardButton(text=title, callback_data=f"category:{cid}")])
    kb_inline = types.InlineKeyboardMarkup(inline_keyboard=items)
    await message.answer("Выберите категорию:", reply_markup=kb_inline)


@dp.callback_query(F.data.regexp(r'(?i)category[:_\-]\d+$') | F.data.startswith("category:") | F.data.startswith("category_") | F.data.startswith("category-"))
async def category_callback(callback: types.CallbackQuery):
    await callback.answer()
    data = callback.data
    cat_id = extract_id_from_callback(data)
    if cat_id is None:
        await callback.message.answer("Не удалось определить категорию.")
        return

    try:
        courses = await db_list_courses_by_category(cat_id)
    except Exception:
        logger.exception("Ошибка получения курсов для категории")
        await callback.message.answer("Ошибка при загрузке курсов.")
        return

    if not courses:
        await callback.message.answer(getattr(texts, "COURSE_EMPTY", "Курсов в этой категории пока нет."))
        return

    # send each course with buy button
    for c in courses:
        course = dict(c) if not isinstance(c, dict) else c
        title = course.get("title")
        desc = course.get("description", "")
        price = course.get("price", 0)
        text = f"<b>{title}</b>\n\n{desc}\n\nЦена: {price} ₽"

        # try to use keyboards.course_inline / buy_kb
        try:
            if kb_course_inline and callable(kb_course_inline):
                kb_markup = kb_course_inline(course if kb_course_inline.__code__.co_argcount >= 1 else (price, course["id"]))
                await callback.message.answer(text, reply_markup=kb_markup)
                continue
        except Exception:
            # fallback to simple inline
            logger.debug("kb.course_inline failed, will use fallback")
        # fallback inline button
        buy_cb = types.InlineKeyboardButton(text=f"💳 Оплатить — {price} ₽", callback_data=f"buy:{course['id']}")
        await callback.message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[buy_cb]]))


# ---------- Buy handler (handles multiple callback formats) ----------
@dp.callback_query(F.data.regexp(r'(?i)^(buy[:_\-]?\d+|.*\bpay[:_\-]?\d+)$') | F.data.contains("buy") )
async def buy_callback(callback: types.CallbackQuery):
    await callback.answer()
    cid = extract_id_from_callback(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить курс для покупки.")
        return

    try:
        course = await db_get_course(cid)
    except Exception:
        logger.exception("Ошибка чтения курса")
        await callback.message.answer("Ошибка при получении курса.")
        return

    if not course:
        await callback.message.answer("Курс не найден.")
        return

    course = dict(course) if not isinstance(course, dict) else course
    price_rub = int(course.get("price", 0))
    if price_rub <= 0:
        await callback.message.answer("Неверная цена курса.")
        return

    if not PAYMENT_PROVIDER_TOKEN:
        await callback.message.answer("Платежная система не настроена. Обратитесь к администратору.")
        return

    try:
        prices = [LabeledPrice(label=course.get("title", "Курс"), amount=price_rub * 100)]
        payload = f"course:{cid}"
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=course.get("title", "Курс"),
            description=course.get("description", "") or "",
            payload=payload,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter=f"purchase_{cid}",
        )
    except Exception:
        logger.exception("send_invoice failed")
        await callback.message.answer("Ошибка отправки инвойса. Проверьте настройку платежного токена.")


@dp.pre_checkout_query()
async def precheckout(q: PreCheckoutQuery):
    try:
        await bot.answer_pre_checkout_query(q.id, ok=True)
    except Exception:
        logger.exception("pre_checkout failed")


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: types.Message):
    try:
        payload = message.successful_payment.invoice_payload or ""
        cid = None
        if payload.startswith("course:"):
            try:
                cid = int(payload.split(":", 1)[1])
            except Exception:
                cid = extract_id_from_callback(payload)
        # record purchase if possible
        if cid and db_record_purchase:
            try:
                await db_record_purchase(message.from_user.id, cid)
            except Exception:
                logger.exception("record_purchase failed")

        # respond with link if course present
        if cid:
            course = await db_get_course(cid)
            if course:
                course = dict(course) if not isinstance(course, dict) else course
                link = course.get("link")
                text = getattr(texts, "random_payment_success", lambda t: f"Оплата принята. Курс «{t}»")(course.get("title"))
                if link:
                    await message.answer(f"{text}\n\nСсылка: {link}")
                    return
        await message.answer("Оплата принята. Если ссылка не была найдена — свяжитесь с администратором.")
    except Exception:
        logger.exception("successful_payment handling failed")
        await message.answer("Оплата принята — произошла внутренняя ошибка при обработке.")


# ---------------- Admin panel shortcuts (robust matching) ----------------

@dp.message(F.text.in_({"👑 Админ-панель", "⚙️ Админ", "⚙️ Админ панель", "Админ"}))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(getattr(texts, "ADMIN_ONLY", "Доступ запрещён."))
        return
    # try admin menu element from keyboards
    kb_menu = None
    if kb_admin_menu:
        try:
            kb_menu = kb_admin_menu()
        except TypeError:
            kb_menu = kb_admin_menu
    if kb_menu is None:
        kb_menu = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="Управление категориями")],
                      [types.KeyboardButton(text="Управление курсами")],
                      [types.KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    await message.answer("Панель администратора:", reply_markup=kb_menu)


# ----- Admin: categories -----
@dp.message(F.text == "Управление категориями")
async def admin_manage_categories(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    cats = await db_list_categories()
    # try to use kb.categories_admin_inline if exists
    try:
        if kb_categories_admin_inline and callable(kb_categories_admin_inline):
            await message.answer("Категории:", reply_markup=kb_categories_admin_inline([dict(c) for c in cats]))
            return
    except Exception:
        logger.debug("kb.categories_admin_inline failed")
    # fallback simple list
    text = "Категории:\n" + "\n".join([f"{c['id']}. {c['title']}" for c in cats])
    await message.answer(text)


@dp.callback_query(F.data.startswith("admin_add_category") | F.data == "admin_add_category")
async def admin_add_category_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Введи название новой категории:", reply_markup=kb_cancel or types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Отмена")]], resize_keyboard=True))
    await state.set_state(AddCategory.waiting_for_title)


@dp.message(StateFilter(AddCategory.waiting_for_title))
async def admin_add_category_finish(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=None)
        return
    if not db_add_category:
        await message.answer("DB: add_category не реализован.")
        await state.clear()
        return
    await db_add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена.")


# ----- Admin: courses management -----
@dp.message(F.text == "Управление курсами")
async def admin_manage_courses(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    # try to use admin_courses inline kb
    try:
        courses = await db_list_courses()
    except Exception:
        logger.exception("list courses failed")
        await message.answer("Ошибка при получении курсов.")
        return

    if not courses:
        await message.answer("Курсов пока нет.")
        return

    try:
        if kb_admin_courses_inline and callable(kb_admin_courses_inline):
            await message.answer("Курсы:", reply_markup=kb_admin_courses_inline([dict(c) for c in courses]))
            return
    except Exception:
        logger.debug("kb.admin_courses_inline failed")

    # fallback: simple list
    text = "Курсы:\n" + "\n".join([f"{c['id']}. {c['title']}" for c in courses])
    await message.answer(text)


@dp.callback_query(F.data.startswith("admin_add_course") | F.data == "admin_add_course")
async def admin_add_course_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    cats = await db_list_categories()
    if not cats:
        await callback.message.answer("Сначала добавьте категорию.")
        return
    # show reply keyboard with categories
    if kb_choose_category and callable(kb_choose_category):
        try:
            kb_markup = kb_choose_category([dict(c) for c in cats])
            await callback.message.answer("Выберите категорию:", reply_markup=kb_markup)
            await state.set_state(AddCourse.waiting_for_category)
            return
        except Exception:
            logger.debug("kb.choose_category failed")
    # fallback manual keyboard
    buttons = [[types.KeyboardButton(text=c['title'])] for c in cats]
    buttons.append([types.KeyboardButton(text="❌ Отмена")])
    kb_rep = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await callback.message.answer("Выберите категорию:", reply_markup=kb_rep)
    await state.set_state(AddCourse.waiting_for_category)


@dp.message(StateFilter(AddCourse.waiting_for_category))
async def admin_add_course_choose_category(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    cats = await db_list_categories()
    chosen = next((c for c in cats if c["title"] == message.text), None)
    if not chosen:
        await message.answer("Выберите категорию кнопкой.")
        return
    await state.update_data(category_id=chosen["id"])
    await state.set_state(AddCourse.waiting_for_title)
    await message.answer("Введите название курса:", reply_markup=kb_cancel or None)


@dp.message(StateFilter(AddCourse.waiting_for_title))
async def admin_add_course_title(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Введите описание курса:")


@dp.message(StateFilter(AddCourse.waiting_for_description))
async def admin_add_course_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Введите цену (в рублях):")


@dp.message(StateFilter(AddCourse.waiting_for_price))
async def admin_add_course_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    if not message.text.isdigit():
        await message.answer("Цена должна быть числом.")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Введите ссылку на курс (URL или текст):")


@dp.message(StateFilter(AddCourse.waiting_for_link))
async def admin_add_course_link(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    data = await state.get_data()
    if not db_add_course:
        await message.answer("DB: add_course не реализован.")
        await state.clear()
        return
    await db_add_course(
        data["category_id"],
        data["title"],
        data["description"],
        data["price"],
        message.text
    )
    await state.clear()
    await message.answer("Курс добавлен.", reply_markup=None)


# ----- Admin: view course -> show admin inline buttons -----
@dp.callback_query(F.data.regexp(r'(?i)^(admin_course[:_\-]?\d+|admin_course_\d+)') | F.data.startswith("admin_course_"))
async def admin_course_callback(callback: types.CallbackQuery):
    await callback.answer()
    cid = extract_id_from_callback(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить курс.")
        return
    c = await db_get_course(cid)
    if not c:
        await callback.message.answer("Курс не найден.")
        return
    course = dict(c) if not isinstance(c, dict) else c
    text = f"<b>{course.get('title')}</b>\n\n{course.get('description')}\n\nЦена: {course.get('price')} ₽\nСсылка: {course.get('link','-')}"
    # use kb.course_admin_inline or fallback
    try:
        if kb_course_admin_inline and callable(kb_course_admin_inline):
            await callback.message.answer(text, reply_markup=kb_course_admin_inline(cid))
            return
    except Exception:
        logger.debug("kb.course_admin_inline failed")
    # fallback
    btns = [[types.InlineKeyboardButton(text="✏ Редактировать", callback_data=f"edit:{cid}")],
            [types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{cid}")]]
    await callback.message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=btns))


@dp.callback_query(F.data.regexp(r'(?i)^(delete[:_\-]?\d+|delete_\d+|delete_course[:_\-]?\d+)$') | F.data.startswith("delete:") | F.data.startswith("delete_course:"))
async def admin_delete_callback(callback: types.CallbackQuery):
    await callback.answer()
    cid = extract_id_from_callback(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить курс для удаления.")
        return
    if not db_delete_course:
        await callback.message.answer("DB: delete_course не реализован.")
        return
    await db_delete_course(cid)
    await callback.message.answer("Курс удалён.")


@dp.callback_query(F.data.regexp(r'(?i)^(edit[:_\-]?\d+|edit_\d+|edit_course[:_\-]?\d+)$') | F.data.startswith("edit:") | F.data.startswith("edit_course:"))
async def admin_edit_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    cid = extract_id_from_callback(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить курс.")
        return
    await state.update_data(course_id=cid)
    # we'll ask fields one by one (title -> description -> price -> link)
    await state.set_state(EditCourse.waiting_for_new_title)
    await callback.message.answer("Введите новое название:", reply_markup=kb_cancel or None)


@dp.message(StateFilter(EditCourse.waiting_for_new_title))
async def admin_edit_title(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    await state.update_data(new_title=message.text)
    await state.set_state(EditCourse.waiting_for_new_description)
    await message.answer("Введите новое описание:")


@dp.message(StateFilter(EditCourse.waiting_for_new_description))
async def admin_edit_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    await state.update_data(new_description=message.text)
    await state.set_state(EditCourse.waiting_for_new_price)
    await message.answer("Введите новую цену (в рублях):")


@dp.message(StateFilter(EditCourse.waiting_for_new_price))
async def admin_edit_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    if not message.text.isdigit():
        await message.answer("Цена должна быть числом.")
        return
    await state.update_data(new_price=int(message.text))
    await state.set_state(EditCourse.waiting_for_new_link)
    await message.answer("Введите новую ссылку:")


@dp.message(StateFilter(EditCourse.waiting_for_new_link))
async def admin_edit_link(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    data = await state.get_data()
    cid = data.get("course_id")
    # prefer db.update_course (full) if present, else call update_course_field for each
    try:
        if hasattr(db, "update_course"):
            await db.update_course(cid, data.get("new_title"), data.get("new_description"), data.get("new_price"), message.text)
        elif db_update_course_field:
            await db_update_course_field(cid, "title", data.get("new_title"))
            await db_update_course_field(cid, "description", data.get("new_description"))
            await db_update_course_field(cid, "price", data.get("new_price"))
            await db_update_course_field(cid, "link", message.text)
        else:
            await message.answer("DB: нет функции для обновления курса.")
            await state.clear()
            return
        await state.clear()
        await message.answer("Курс обновлён.")
    except Exception:
        logger.exception("update course failed")
        await message.answer("Ошибка при обновлении курса.")
        await state.clear()

# global cancel handler
@dp.message(F.text == "❌ Отмена")
async def cancel_any(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(getattr(texts, "CANCELLED", "Отменено."))

# fallback
@dp.message()
async def fallback(message: types.Message):
    try:
        txt = texts.random_fallback()
    except Exception:
        txt = "Не понял. Используй меню."
    await message.answer(txt)

# run
async def main():
    try:
        await db.init_db()
    except Exception:
        logger.exception("init_db failed at startup")
    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot)
    except Exception:
        logger.exception("Polling stopped due to exception")
        raise

if __name__ == "__main__":
    asyncio.run(main())





