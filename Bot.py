# Bot.py (Aiogram 3.6) — полный рабочий файл
import asyncio
import logging
import os
import re
from typing import Any, Callable, Optional

from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import db
import keyboards as kb

# ---------- config & logging ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_PROVIDER_TOKEN = (
    os.getenv("PAYMENT_PROVIDER_TOKEN")
    or os.getenv("PAYMENTS_TOKEN")
    or os.getenv("PAYMENTS_PROVIDER_TOKEN")
    or ""
)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ---------- helper utilities ----------
def pick_kb(*names: str, default: Optional[Any] = None) -> Any:
    """
    Try to get first existing attribute from keyboards module by names.
    Returns attribute or default.
    """
    for n in names:
        if hasattr(kb, n):
            return getattr(kb, n)
    return default


def extract_int(s: str) -> Optional[int]:
    if not s:
        return None
    m = re.search(r"(\d+)(?!.*\d)", s)
    return int(m.group(1)) if m else None


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# keyboard accessors (try several names for resilience)
kb_main = pick_kb("main_menu", "main_kb", "main")
kb_admin_menu = pick_kb("admin_menu", "admin_panel", "admin_main_kb", "admin_menu_kb")
kb_cancel = pick_kb("cancel_kb", "cancel_keyboard", "cancel")
kb_categories_inline = pick_kb("categories_inline", "categories_keyboard", "categories_inline_kb", "categories_keyboard")
kb_courses_inline = pick_kb("courses_inline", "courses_keyboard", "courses_inline_kb", "courses_keyboard")
kb_course_actions = pick_kb("course_keyboard", "course_actions", "buy_kb")
kb_admin_edit_inline = pick_kb("edit_delete_inline", None)


# ---------- FSM States ----------
class CategoryStates(StatesGroup):
    adding = State()
    editing_id = State()
    editing_title = State()


class CourseStates(StatesGroup):
    choosing_category = State()
    adding_title = State()
    adding_description = State()
    adding_price = State()
    adding_link = State()
    editing_course_id = State()
    editing_field = State()
    editing_value = State()


# ---------- Startup ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    admin = is_admin(message.from_user.id)
    # ensure DB tables
    try:
        if hasattr(db, "create_tables"):
            await db.create_tables()
        elif hasattr(db, "init_db"):
            await db.init_db()
    except Exception:
        logger.exception("DB initialization error (ignored)")

    # build menu
    try:
        if callable(kb_main):
            menu = kb_main(admin) if callable(kb_main) and kb_main.__code__.co_argcount >= 1 else kb_main
        else:
            buttons = [[types.KeyboardButton(text="📚 Курсы")], [types.KeyboardButton(text="ℹ️ О боте")]]
            if admin:
                buttons.append([types.KeyboardButton(text="⚙️ Админ-панель")])
            menu = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    except Exception:
        menu = None

    await message.answer(
        "Привет. Я — циничный ИИ-ментор. Выбирай меню.",
        reply_markup=menu
    )


# ---------- About ----------
@dp.message(F.text == "ℹ️ О боте")
async def about_handler(message: Message):
    await message.answer("Немного сарказма, немного практики. Я помогаю становиться лучше — если ты этого хочешь.")


# ---------- Show categories (user) ----------
@dp.message(F.text == "📚 Курсы")
async def list_categories(message: Message):
    try:
        cats = await db.get_categories()
    except Exception:
        logger.exception("get_categories failed")
        cats = []

    if not cats:
        await message.answer("Категорий пока нет.")
        return

    # adapt categories to dicts with id/title
    adapted = []
    for c in cats:
        if isinstance(c, dict):
            title = c.get("title") or c.get("name") or c.get("title_en") or str(c.get("id"))
            adapted.append({"id": c["id"], "title": title})
        else:
            # if row tuple (id, title)
            adapted.append({"id": c[0], "title": c[1]})
    # try to use keyboard builder from kb
    markup = None
    try:
        if callable(kb_categories_inline):
            # some functions expect list of dicts
            markup = kb_categories_inline(adapted)
    except Exception:
        markup = None

    if markup is None:
        markup = InlineKeyboardMarkup()
        for c in adapted:
            markup.add(InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}"))

    await message.answer("Выбирай категорию:", reply_markup=markup)


@dp.callback_query(F.data.startswith("category:"))
async def category_cb(callback: CallbackQuery):
    await callback.answer()
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить категорию.")
        return
    try:
        courses = await db.get_courses(cid)
    except Exception:
        logger.exception("get_courses failed")
        courses = []

    if not courses:
        await callback.message.answer("Курсов в этой категории пока нет.")
        return

    # adapt and send courses (title + description) with buy button only
    adapted = []
    for r in courses:
        if isinstance(r, dict):
            adapted.append(r)
        else:
            # try tuple format
            # expected: (id, title, description, price, link)
            adapted.append({
                "id": r[0],
                "title": r[1] if len(r) > 1 else "",
                "description": r[2] if len(r) > 2 else "",
                "price": r[3] if len(r) > 3 else 0,
                "link": r[4] if len(r) > 4 else ""
            })

    for course in adapted:
        title = course.get("title") or "Курс"
        descr = course.get("description") or ""
        text = f"<b>{title}</b>\n\n{descr}"
        # try kb course actions (buy button shows price)
        try:
            if callable(kb_course_actions):
                btn = kb_course_actions(course["id"])
            elif callable(kb_courses_inline):
                # some kbs expect list
                btn = kb_courses_inline([course])
            else:
                raise Exception("no kb course buy builder")
        except Exception:
            # fallback build
            btn = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 Купить ({int(course.get('price',0))} ₽)", callback_data=f"buy:{course['id']}")]
            ])
        await callback.message.answer(text, reply_markup=btn)


# ---------- Payment handlers ----------
@dp.callback_query(F.data.startswith("buy:"))
async def buy_cb(callback: CallbackQuery):
    await callback.answer()
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка: не могу определить курс для оплаты.")
        return
    try:
        course = await db.get_course(cid)
    except Exception:
        logger.exception("get_course failed")
        course = None
    if not course:
        await callback.message.answer("Курс не найден.")
        return

    price = int(course.get("price", 0))
    if price <= 0:
        await callback.message.answer("Неверная цена для курса.")
        return
    if not PAYMENT_PROVIDER_TOKEN:
        await callback.message.answer("Платежная система не настроена. Обратитесь к администратору.")
        return

    prices = [LabeledPrice(label=course.get("title", "Курс"), amount=price * 100)]
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=course.get("title", "Курс"),
            description=(course.get("description") or "")[:800],
            payload=f"course:{cid}",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter=f"course_{cid}"
        )
    except Exception:
        logger.exception("send_invoice failed")
        await callback.message.answer("Ошибка отправки инвойса. Проверь PAYMENT_PROVIDER_TOKEN.")


@dp.pre_checkout_query()
async def precheckout(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    try:
        payload = message.successful_payment.invoice_payload or ""
        cid = extract_int(payload)
        if cid is None:
            await message.answer("Оплата принята, но не удалось найти курс.")
            return
        course = await db.get_course(cid)
        if not course:
            await message.answer("Оплата принята, но курс не найден.")
            return
        link = course.get("link") or course.get("url") or ""
        if link:
            await message.answer(f"Оплата принята. Ссылка: {link}")
        else:
            await message.answer("Оплата принята. Ссылка не найдена — обратитесь к администратору.")
    except Exception:
        logger.exception("successful_payment handler error")
        await message.answer("Оплата принята — произошла ошибка при обработке.")


# ---------- Admin panel (message triggers) ----------
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        menu = kb_admin_menu() if callable(kb_admin_menu) else kb_admin_menu
    except Exception:
        # fallback
        menu = types.ReplyKeyboardMarkup(keyboard=[
            [types.KeyboardButton(text="➕ Добавить категорию")],
            [types.KeyboardButton(text="➕ Добавить курс")],
            [types.KeyboardButton(text="📂 Управление категориями")],
            [types.KeyboardButton(text="📘 Управление курсами")],
            [types.KeyboardButton(text="❌ Отмена")]
        ], resize_keyboard=True)
    await message.answer("Панель администратора:", reply_markup=menu)


# ---------- Categories management ----------
@dp.message(F.text == "➕ Добавить категорию")
async def start_add_category(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(CategoryStates := CategoryStates if False else CategoryStates)  # placeholder to appease type check
    # we will use CategoryStates.adding, but to avoid repeated name errors, reference explicitly:
    await state.set_state(CategoryStates.adding)
    cancel_markup = kb_cancel() if callable(kb_cancel) else types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)
    await message.answer("Введи название новой категории (или ❌ Отмена):", reply_markup=cancel_markup)


@dp.message(StateFilter(CategoryStates.adding))
async def finish_add_category(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
        return
    try:
        await db.add_category(message.text)
        await state.clear()
        await message.answer("Категория добавлена.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
    except Exception:
        logger.exception("add_category failed")
        await message.answer("Ошибка при добавлении категории.")
        await state.clear()


@dp.message(F.text == "📂 Управление категориями")
async def manage_categories(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        cats = await db.get_categories()
    except Exception:
        logger.exception("get_categories failed")
        cats = []
    if not cats:
        await message.answer("Категорий нет.")
        return
    adapted = [{"id": c["id"], "title": c.get("title") or c.get("name") or c.get("name_en") or str(c.get("id"))} if isinstance(c, dict) else {"id": c[0], "title": c[1]} for c in cats]
    try:
        inline = kb_admin_edit_inline("category", adapted) if callable(kb_admin_edit_inline) else None
    except Exception:
        inline = None
    if inline is None:
        inline = InlineKeyboardMarkup()
        for c in adapted:
            inline.add(InlineKeyboardButton(text=f"✏️ {c['title']}", callback_data=f"edit_category:{c['id']}"))
            inline.add(InlineKeyboardButton(text=f"🗑 {c['title']}", callback_data=f"delete_category:{c['id']}"))
    await message.answer("Категории:", reply_markup=inline)


@dp.callback_query(F.data.startswith("delete_category:"))
async def delete_category(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    try:
        await db.delete_category(cid)
        await callback.message.answer("Категория удалена.")
    except Exception:
        logger.exception("delete_category failed")
        await callback.message.answer("Ошибка при удалении категории.")


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
    await state.set_state(CategoryStates.editing_title)
    cancel_markup = kb_cancel() if callable(kb_cancel) else types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)
    await callback.message.answer("Введи новое название категории (или ❌ Отмена):", reply_markup=cancel_markup)


@dp.message(StateFilter(CategoryStates.editing_title))
async def edit_category_finish(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
        return
    data = await state.get_data()
    cid = data.get("edit_cat_id")
    if cid is None:
        await message.answer("Нет выбранной категории.")
        await state.clear()
        return
    # try update_category else fallback: delete+add (not ideal)
    try:
        if hasattr(db, "update_category"):
            await db.update_category(cid, message.text)
        else:
            # fallback: delete and add new one
            await db.delete_category(cid)
            await db.add_category(message.text)
        await state.clear()
        await message.answer("Категория обновлена.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
    except Exception:
        logger.exception("update category failed")
        await message.answer("Ошибка при обновлении категории.")
        await state.clear()


# ---------- Courses management: add/edit/delete ----------
@dp.message(F.text == "➕ Добавить курс")
async def start_add_course(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        cats = await db.get_categories()
    except Exception:
        logger.exception("get_categories failed")
        cats = []
    if not cats:
        await message.answer("Сначала добавь категорию.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
        return
    # show categories inline to choose where to add
    adapted = [{"id": c["id"], "title": c.get("title") or c.get("name") or str(c.get("id"))} if isinstance(c, dict) else {"id": c[0], "title": c[1]} for c in cats]
    try:
        markup = kb_categories_inline(adapted) if callable(kb_categories_inline) else None
    except Exception:
        markup = None
    if markup is None:
        markup = InlineKeyboardMarkup()
        for c in adapted:
            markup.add(InlineKeyboardButton(text=c["title"], callback_data=f"choose_cat_for_add:{c['id']}"))
    await state.set_state(CourseStates.choosing_category)
    await message.answer("Выбери категорию для нового курса:", reply_markup=markup)


@dp.callback_query(StateFilter(CourseStates.choosing_category))
async def choose_category_for_add(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    # allow either callback like choose_cat_for_add:ID or category:ID
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить категорию.")
        return
    await state.update_data(category_id=cid)
    await state.set_state(CourseStates.adding_title)
    cancel_markup = kb_cancel() if callable(kb_cancel) else types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)
    await callback.message.answer("Введите название курса (или ❌ Отмена):", reply_markup=cancel_markup)


@dp.message(StateFilter(CourseStates.adding_title))
async def add_course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
        return
    await state.update_data(title=message.text)
    await state.set_state(CourseStates.adding_description)
    await message.answer("Введите описание курса (или ❌ Отмена):", reply_markup=kb_cancel() if callable(kb_cancel) else None)


@dp.message(StateFilter(CourseStates.adding_description))
async def add_course_description(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
        return
    await state.update_data(description=message.text)
    await state.set_state(CourseStates.adding_price)
    await message.answer("Введите цену (целое число, рубли) (или ❌ Отмена):", reply_markup=kb_cancel() if callable(kb_cancel) else None)


@dp.message(StateFilter(CourseStates.adding_price))
async def add_course_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
        return
    if not message.text.isdigit():
        await message.answer("Цена должна быть числом. Попробуйте ещё раз.")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(CourseStates.adding_link)
    await message.answer("Вставьте ссылку на курс (или ❌ Отмена):", reply_markup=kb_cancel() if callable(kb_cancel) else None)


@dp.message(StateFilter(CourseStates.adding_link))
async def add_course_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
        return
    data = await state.get_data()
    cid = data.get("category_id")
    title = data.get("title")
    description = data.get("description")
    price = data.get("price")
    link = message.text
    if None in (cid, title, description, price):
        await message.answer("Недостаточно данных, операция отменена.")
        await state.clear()
        return
    try:
        # try db.add_course signature (category_id, title, description, price, link)
        await db.add_course(cid, title, description, price, link)
    except TypeError:
        # try alternative signature add_course(title, description, price, link, category_id)
        try:
            await db.add_course(title, description, price, link, cid)
        except Exception:
            logger.exception("add_course failed")
            await message.answer("Ошибка при добавлении курса.")
            await state.clear()
            return
    except Exception:
        logger.exception("add_course failed")
        await message.answer("Ошибка при добавлении курса.")
        await state.clear()
        return

    await state.clear()
    await message.answer("Курс успешно добавлен.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)


@dp.message(F.text == "📘 Управление курсами")
async def manage_courses(message: Message):
    if not is_admin(message.from_user.id):
        return
    # gather all courses
    courses_all = []
    try:
        cats = await db.get_categories()
    except Exception:
        logger.exception("get_categories failed")
        cats = []
    for c in cats:
        try:
            cs = await db.get_courses(c["id"])
        except Exception:
            cs = []
        for course in cs:
            courses_all.append(course)
    if not courses_all:
        await message.answer("Курсов нет.")
        return
    adapted = []
    for c in courses_all:
        if isinstance(c, dict):
            adapted.append({"id": c["id"], "title": c.get("title") or c.get("name") or ""})
        else:
            adapted.append({"id": c[0], "title": c[1]})
    try:
        inline = kb_admin_edit_inline("course", adapted) if callable(kb_admin_edit_inline) else None
    except Exception:
        inline = None
    if inline is None:
        inline = InlineKeyboardMarkup()
        for c in adapted:
            inline.add(InlineKeyboardButton(text=f"✏️ {c['title']}", callback_data=f"edit_course:{c['id']}"))
            inline.add(InlineKeyboardButton(text=f"🗑 {c['title']}", callback_data=f"delete_course:{c['id']}"))
    await message.answer("Курсы:", reply_markup=inline)


@dp.callback_query(F.data.startswith("delete_course:"))
async def delete_course_cb(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    try:
        await db.delete_course(cid)
        await callback.message.answer("Курс удалён.")
    except Exception:
        logger.exception("delete_course failed")
        await callback.message.answer("Ошибка при удалении курса.")


@dp.callback_query(F.data.startswith("edit_course:"))
async def edit_course_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка.")
        return
    await state.update_data(edit_course_id=cid)
    await state.set_state(CourseStates.editing_field)
    # ask which field
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data=f"edit_field:name:{cid}")],
        [InlineKeyboardButton(text="Описание", callback_data=f"edit_field:description:{cid}")],
        [InlineKeyboardButton(text="Цена", callback_data=f"edit_field:price:{cid}")],
        [InlineKeyboardButton(text="Ссылка", callback_data=f"edit_field:link:{cid}")]
    ])
    await callback.message.answer("Что редактируем?", reply_markup=markup)


@dp.callback_query(F.data.regexp(r"^edit_field:(name|description|price|link):\d+$"))
async def edit_field_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    field = parts[1]
    cid = int(parts[2])
    await state.update_data(edit_course_id=cid, edit_field=field)
    await state.set_state(CourseStates.editing_value)
    cancel_markup = kb_cancel() if callable(kb_cancel) else types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)
    await callback.message.answer(f"Введи новое значение для {field} (или ❌ Отмена):", reply_markup=cancel_markup)


@dp.message(StateFilter(CourseStates.editing_value))
async def save_edited_course_field(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
        return
    data = await state.get_data()
    cid = data.get("edit_course_id")
    field = data.get("edit_field")
    if cid is None or not field:
        await message.answer("Нет данных для редактирования.")
        await state.clear()
        return
    try:
        # prefer update_course (full) if available
        if hasattr(db, "update_course"):
            cur = await db.get_course(cid)
            if not cur:
                await message.answer("Курс не найден.")
                await state.clear()
                return
            title = cur.get("title")
            description = cur.get("description")
            price = cur.get("price")
            link = cur.get("link")
            if field in ("name", "title"):
                title = message.text
            elif field == "description":
                description = message.text
            elif field == "price":
                try:
                    price = int(message.text)
                except ValueError:
                    await message.answer("Цена должна быть числом.")
                    return
            elif field == "link":
                link = message.text
            await db.update_course(cid, title, description, price, link)
        elif hasattr(db, "update_course_field"):
            await db.update_course_field(cid, field, message.text)
        else:
            await message.answer("Функция обновления курса не реализована в db.py.")
            await state.clear()
            return
        await state.clear()
        await message.answer("Курс обновлён.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
    except Exception:
        logger.exception("update course failed")
        await message.answer("Ошибка при обновлении курса.")
        await state.clear()


# ---------- Global cancel ----------
@dp.message(F.text == "❌ Отмена")
async def global_cancel(message: Message, state: FSMContext):
    await state.clear()
    if is_admin(message.from_user.id):
        await message.answer("Отменено.", reply_markup=kb_admin_menu() if callable(kb_admin_menu) else None)
    else:
        await message.answer("Отменено.", reply_markup=kb_main(True) if callable(kb_main) else None)


# ---------- Debug callback (catch-all to avoid unhandled updates) ----------
@dp.callback_query()
async def catch_all_callbacks(cb: CallbackQuery):
    # log data so we can inspect unexpected callback_data
    logger.debug("Unhandled callback_data: %s from user=%s", cb.data, cb.from_user.id)
    # always answer to remove client spinner
    await cb.answer()


# ---------- Run ----------
async def main():
    # try to ensure tables exist
    try:
        if hasattr(db, "create_tables"):
            await db.create_tables()
        elif hasattr(db, "init_db"):
            await db.init_db()
    except Exception:
        logger.exception("DB init failed at startup (ignored)")
    logger.info("Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
