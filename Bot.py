# Bot.py — Aiogram 3.6 compatible — full bot
import asyncio
import logging
import os
import re
from dotenv import load_dotenv

load_dotenv()

from typing import Optional

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

# local modules (must exist)
import db
import keyboards as kb
import states as st

# ---------------- Config & Logging ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN") or os.getenv("PAYMENTS_TOKEN") or ""
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ---------------- Helpers ----------------
def extract_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = re.search(r"(\d+)(?!.*\d)", s)
    return int(m.group(1)) if m else None


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def safe_kb(func_name: str, *args, default=None):
    """
    Try to call keyboards.<func_name>(*args). If missing or fails, return default.
    """
    fn = getattr(kb, func_name, None)
    if not callable(fn):
        return default
    try:
        return fn(*args)
    except Exception as e:
        logger.exception("Keyboard builder %s failed: %s", func_name, e)
        return default


# ---------------- Startup (ensure DB) ----------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Ensure DB tables exist (support both create_tables and init_db)
    try:
        if hasattr(db, "create_tables"):
            await db.create_tables()
        elif hasattr(db, "init_db"):
            await db.init_db()
        elif hasattr(db, "init_db_sync"):
            await db.init_db_sync()
    except Exception:
        logger.exception("DB initialization failed (ignored)")

    admin_flag = is_admin(message.from_user.id)
    main = safe_kb("main_menu", admin_flag)
    if main is None:
        # fallback
        kb_buttons = [[types.KeyboardButton(text="📚 Курсы")], [types.KeyboardButton(text="ℹ️ О боте")]]
        if admin_flag:
            kb_buttons.append([types.KeyboardButton(text="⚙️ Админ-панель")])
        main = types.ReplyKeyboardMarkup(keyboard=kb_buttons, resize_keyboard=True)

    await message.answer(
        "Привет. Я — твой слегка циничный ИИ-наставник. Выбери действие.",
        reply_markup=main,
    )


# ---------------- About ----------------
@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message):
    await message.answer(
        "Я — немного циничный ИИ с глубокой философией. Помогаю людям становиться лучше — честно и без украшательств."
    )


# ---------------- List categories -> show courses ----------------
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    try:
        cats = await db.get_categories()
    except Exception:
        logger.exception("get_categories failed")
        cats = []

    if not cats:
        await message.answer("Категорий пока нет.")
        return

    # normalize categories to list of dicts with id & title/name
    adapted = []
    for c in cats:
        if isinstance(c, dict):
            title = c.get("title") or c.get("name") or c.get("title_en") or ""
            adapted.append({"id": c["id"], "title": title})
        else:
            # tuple fallback
            adapted.append({"id": c[0], "title": c[1]})

    markup = safe_kb("categories_inline", adapted)
    if markup is None:
        buttons = [[InlineKeyboardButton(text=c["title"], callback_data=f"category:{c['id']}")] for c in adapted]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer("Выбирай категорию:", reply_markup=markup)


@dp.callback_query(F.data.startswith("category:") | F.data.startswith("cat_"))
async def on_category(callback: CallbackQuery):
    await callback.answer()
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить категорию.")
        return
    try:
        courses = await db.get_courses(cid)
    except Exception:
        # try alternative name
        try:
            courses = await db.get_courses_by_category(cid)
        except Exception:
            logger.exception("get_courses failed")
            courses = []

    if not courses:
        await callback.message.answer("В этой категории пока нет курсов.")
        return

    # normalize courses
    adapted = []
    for r in courses:
        if isinstance(r, dict):
            adapted.append(r)
        else:
            # tuple fallback (id, title, description, price, link)
            adapted.append({
                "id": r[0],
                "title": r[1] if len(r) > 1 else "",
                "description": r[2] if len(r) > 2 else "",
                "price": r[3] if len(r) > 3 else 0,
                "link": r[4] if len(r) > 4 else ""
            })

    for course in adapted:
        title = course.get("title") or "Курс"
        desc = course.get("description") or ""
        text = f"<b>{title}</b>\n\n{desc}"
        # buy button builder
        buy_markup = safe_kb("courses_inline", [course])
        if buy_markup is None:
            buy_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"💳 Купить ({int(course.get('price', 0))} ₽)",
                                          callback_data=f"buy:{course['id']}")]
                ]
            )
        await callback.message.answer(text, reply_markup=buy_markup)


# ---------------- Payments ----------------
@dp.callback_query(F.data.startswith("buy:"))
async def on_buy(callback: CallbackQuery):
    await callback.answer()
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Ошибка покупки.")
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
        await callback.message.answer("Неверная цена.")
        return

    if not PAYMENT_PROVIDER_TOKEN:
        await callback.message.answer("Платежный провайдер не настроен. Свяжитесь с админом.")
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
        await callback.message.answer("Ошибка отправки инвойса. Проверь конфигурацию платежей.")


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    try:
        payload = (message.successful_payment and message.successful_payment.invoice_payload) or ""
        cid = extract_int(payload)
        if cid is None:
            await message.answer("Оплата принята, но не удалось определить курс.")
            return
        course = await db.get_course(cid)
        if not course:
            await message.answer("Оплата принята, но курс не найден.")
            return
        link = course.get("link") or course.get("url") or ""
        if link:
            await message.answer(f"✅ Оплата прошла успешно! Вот ссылка:\n{link}")
        else:
            await message.answer("✅ Оплата прошла успешно. Ссылка отсутствует — свяжитесь с админом.")
    except Exception:
        logger.exception("successful_payment handler error")
        await message.answer("Оплата принята — произошла ошибка при обработке.")


# ---------------- Admin Panel (reply-keyboard triggers) ----------------
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ-панели.")
        return
    admin_kb = safe_kb("admin_menu")
    if admin_kb is None:
        admin_kb = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="➕ Добавить категорию")],
                [types.KeyboardButton(text="📂 Управление категориями")],
                [types.KeyboardButton(text="➕ Добавить курс")],
                [types.KeyboardButton(text="📘 Управление курсами")],
                [types.KeyboardButton(text="❌ Отмена")]
            ],
            resize_keyboard=True
        )
    await message.answer("Панель администратора:", reply_markup=admin_kb)


# ---------- Categories management ----------
@dp.message(F.text == "➕ Добавить категорию")
async def start_add_category(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    cancel = safe_kb("cancel_kb")
    if cancel is None:
        cancel = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)
    await state.set_state(st.AddCategory.waiting_for_title)
    await message.answer("Введите название категории (или ❌ Отмена):", reply_markup=cancel)


@dp.message(StateFilter(st.AddCategory.waiting_for_title))
async def finish_add_category(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление категории отменено.", reply_markup=safe_kb("admin_menu") or safe_kb("main_menu", True))
        return
    try:
        await db.add_category(message.text)
        await state.clear()
        await message.answer(f"Категория <b>{message.text}</b> добавлена.", reply_markup=safe_kb("admin_menu"))
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

    adapted = [{"id": c["id"], "title": c.get("title") or c.get("name") or c.get("title_en") or c.get("name")} if isinstance(c, dict) else {"id": c[0], "title": c[1]} for c in cats]

    inline = safe_kb("edit_delete_inline", "category", adapted)
    if inline is None:
        buttons = [[InlineKeyboardButton(text=f"✏️ {c['title']}", callback_data=f"edit_category:{c['id']}"),
                    InlineKeyboardButton(text=f"🗑 {c['title']}", callback_data=f"delete_category:{c['id']}")] for c in adapted]
        inline = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer("Категории:", reply_markup=inline)


@dp.callback_query(F.data.startswith("delete_category:") | F.data.startswith("delcat_"))
async def delete_category(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить категорию.")
        return
    try:
        await db.delete_category(cid)
        await callback.message.answer("Категория удалена.")
    except Exception:
        logger.exception("delete_category failed")
        await callback.message.answer("Ошибка при удалении категории.")


@dp.callback_query(F.data.startswith("edit_category:") | F.data.startswith("edit_category_"))
async def edit_category_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить категорию.")
        return
    await state.update_data(edit_cat_id=cid)
    await state.set_state(st.EditCategory.waiting_for_new_title)
    cancel = safe_kb("cancel_kb") or types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)
    await callback.message.answer("Введите новое название (или ❌ Отмена):", reply_markup=cancel)


@dp.message(StateFilter(st.EditCategory.waiting_for_new_title))
async def edit_category_finish(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=safe_kb("admin_menu"))
        return
    data = await state.get_data()
    cid = data.get("edit_cat_id")
    if cid is None:
        await message.answer("Нет выбранной категории.")
        await state.clear()
        return
    try:
        if hasattr(db, "update_category"):
            await db.update_category(cid, message.text)
        else:
            # fallback: delete + add
            await db.delete_category(cid)
            await db.add_category(message.text)
        await state.clear()
        await message.answer("Категория обновлена.", reply_markup=safe_kb("admin_menu"))
    except Exception:
        logger.exception("update_category failed")
        await message.answer("Ошибка при обновлении категории.")
        await state.clear()


# ---------------- Courses: add / manage ----------------
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
        await message.answer("Сначала добавьте категорию.", reply_markup=safe_kb("admin_menu"))
        return

    adapted = [{"id": c["id"], "title": c.get("title") or c.get("name") or c.get("title_en") or c.get("name")} if isinstance(c, dict) else {"id": c[0], "title": c[1]} for c in cats]
    markup = safe_kb("categories_inline", adapted)
    if markup is None:
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c["title"], callback_data=f"choose_cat_for_add:{c['id']}")] for c in adapted])

    await state.set_state(st.AddCourse.choosing_category)
    await message.answer("Выберите категорию для нового курса:", reply_markup=markup)


@dp.callback_query(StateFilter(st.AddCourse.choosing_category))
async def choose_category_for_add(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить категорию.")
        return
    await state.update_data(category_id=cid)
    await state.set_state(st.AddCourse.waiting_for_title)
    cancel = safe_kb("cancel_kb") or types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)
    await callback.message.answer("Введите название курса (или ❌ Отмена):", reply_markup=cancel)


@dp.message(StateFilter(st.AddCourse.waiting_for_title))
async def add_course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=safe_kb("admin_menu"))
        return
    await state.update_data(title=message.text)
    await state.set_state(st.AddCourse.waiting_for_description)
    await message.answer("Введите описание курса (или ❌ Отмена):", reply_markup=safe_kb("cancel_kb"))


@dp.message(StateFilter(st.AddCourse.waiting_for_description))
async def add_course_description(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=safe_kb("admin_menu"))
        return
    await state.update_data(description=message.text)
    await state.set_state(st.AddCourse.waiting_for_price)
    await message.answer("Введите цену (целое число, рубли) (или ❌ Отмена):", reply_markup=safe_kb("cancel_kb"))


@dp.message(StateFilter(st.AddCourse.waiting_for_price))
async def add_course_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=safe_kb("admin_menu"))
        return
    if not message.text.isdigit():
        await message.answer("Цена должна быть целым числом. Попробуйте снова.")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(st.AddCourse.waiting_for_link)
    await message.answer("Вставьте ссылку на курс (или ❌ Отмена):", reply_markup=safe_kb("cancel_kb"))


@dp.message(StateFilter(st.AddCourse.waiting_for_link))
async def add_course_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=safe_kb("admin_menu"))
        return
    data = await state.get_data()
    cid = data.get("category_id")
    title = data.get("title")
    description = data.get("description")
    price = data.get("price")
    link = message.text
    if None in (cid, title, description, price):
        await state.clear()
        await message.answer("Не все данные присутствуют. Операция отменена.", reply_markup=safe_kb("admin_menu"))
        return

    try:
        # Try common db.add_course signature: (category_id, title, description, price, link)
        await db.add_course(cid, title, description, price, link)
    except TypeError:
        # try alternative signatures (title, desc, price, link, category_id)
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
    await message.answer("Курс успешно добавлен.", reply_markup=safe_kb("admin_menu"))


# ---------------- Manage courses (edit/delete) ----------------
@dp.message(F.text == "📘 Управление курсами")
async def manage_courses(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        cats = await db.get_categories()
    except Exception:
        logger.exception("get_categories failed")
        cats = []

    courses_all = []
    for c in cats:
        try:
            cs = await db.get_courses(c["id"])
        except Exception:
            cs = []
        for cr in cs:
            courses_all.append(cr)

    if not courses_all:
        await message.answer("Курсов нет.")
        return

    adapted = [{"id": c["id"], "title": c.get("title") or c.get("name") or c.get("title", "")} if isinstance(c, dict) else {"id": c[0], "title": c[1]} for c in courses_all]
    inline = safe_kb("edit_delete_inline", "course", adapted)
    if inline is None:
        buttons = [[InlineKeyboardButton(text=f"✏️ {c['title']}", callback_data=f"edit_course:{c['id']}"),
                    InlineKeyboardButton(text=f"🗑 {c['title']}", callback_data=f"delete_course:{c['id']}")] for c in adapted]
        inline = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Курсы:", reply_markup=inline)


@dp.callback_query(F.data.startswith("delete_course:") | F.data.startswith("delcourse_"))
async def delete_course(callback: CallbackQuery):
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


@dp.callback_query(F.data.startswith("edit_course:") | F.data.startswith("edit_course_"))
async def edit_course_start(callback: CallbackQuery, state: FSMContext):
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
    ])
    await callback.message.answer("Выберите поле для редактирования:", reply_markup=markup)


@dp.callback_query(F.data.regexp(r"^edit_course_field:(title|description|price|link):\d+$"))
async def edit_course_field_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    field = parts[1]
    cid = int(parts[2])
    await state.update_data(edit_course_id=cid, edit_field=field)
    await state.set_state(st.EditCourse.waiting_for_new_value)
    cancel = safe_kb("cancel_kb") or types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)
    await callback.message.answer(f"Введи новое значение для {field} (или ❌ Отмена):", reply_markup=cancel)


@dp.message(StateFilter(st.EditCourse.waiting_for_new_value))
async def save_edited_course_value(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=safe_kb("admin_menu"))
        return
    data = await state.get_data()
    cid = data.get("edit_course_id")
    field = data.get("edit_field")
    if cid is None or not field:
        await message.answer("Нет данных для редактирования.")
        await state.clear()
        return
    value = int(message.text) if field == "price" and message.text.isdigit() else message.text
    try:
        if hasattr(db, "update_course_field"):
            await db.update_course_field(cid, field, value)
        elif hasattr(db, "get_course") and hasattr(db, "update_course"):
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
                price = int(value)
            elif field == "link":
                link = value
            await db.update_course(cid, title, description, price, link)
        else:
            await message.answer("Функция обновления курса не реализована в db.py.")
            await state.clear()
            return
        await state.clear()
        await message.answer("Курс обновлён.", reply_markup=safe_kb("admin_menu"))
    except Exception:
        logger.exception("update course failed")
        await message.answer("Ошибка при обновлении курса.")
        await state.clear()


# ---------------- Global cancel handler ----------------
@dp.message(F.text == "❌ Отмена")
async def cancel_global(message: Message, state: FSMContext):
    await state.clear()
    if is_admin(message.from_user.id):
        await message.answer("Отменено.", reply_markup=safe_kb("admin_menu"))
    else:
        await message.answer("Отменено.", reply_markup=safe_kb("main_menu", False))


# ---------------- Debug fallback for callbacks (to avoid 'not handled') ----------------
@dp.callback_query()
async def catchall_callback(cb: CallbackQuery):
    logger.debug("Unhandled callback_data: %s from user %s", cb.data, cb.from_user.id)
    # always answer to remove client 'loading' UI
    await cb.answer()


# ---------------- Run ----------------
async def main():
    # ensure tables at startup if DB exposes create_tables/init_db
    try:
        if hasattr(db, "create_tables"):
            await db.create_tables()
        elif hasattr(db, "init_db"):
            await db.init_db()
    except Exception:
        logger.exception("DB init at startup failed (ignored)")

    logger.info("Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())



