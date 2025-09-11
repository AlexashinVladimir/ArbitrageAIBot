# Bot.py — полный рабочий основной файл (Aiogram 3.6)
import asyncio
import logging
import os
import re
from typing import Callable, Optional, Any

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery

# локальные модули (должны существовать в проекте)
import db
import keyboards as kb
from states import AddCategory, AddCourse, EditCourse

# ----------------- Конфигурация и логирование -----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
# Поддерживаем несколько названий переменной окружения для совместимости
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN") or os.getenv("PROVIDER_TOKEN") or os.getenv("PAYMENTS_PROVIDER_TOKEN") or ""

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env")

# Инициализация бота и диспетчера (с рекомендованным способом указания parse_mode)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ----------------- Вспомогательные функции (совместимость с db/keyboards) -----------------
def resolve(obj: Any, *names: str) -> Optional[Callable]:
    """
    Попытаться найти в obj функцию/атрибут под одним из имён в names.
    Возвращает callable или значение или None.
    """
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return None


def extract_id(data: str) -> Optional[int]:
    """Извлечь последнее целое число из callback_data или строки."""
    if not data:
        return None
    m = re.search(r"(\d+)(?!.*\d)", data)
    return int(m.group(1)) if m else None


# Resolve DB functions (поддерживаем разные имена)
db_init = resolve(db, "init_db")
db_list_categories = resolve(db, "list_categories", "get_categories", "list_categories")
db_add_category = resolve(db, "add_category", "create_category")
db_list_courses = resolve(db, "list_courses", "get_courses")
db_list_courses_by_category = resolve(db, "list_courses_by_category", "get_courses_by_category", "list_courses_by_category")
db_get_course = resolve(db, "get_course", "get_course_by_id", "fetch_course")
db_add_course = resolve(db, "add_course", "create_course")
db_update_course_field = resolve(db, "update_course_field", "update_course")
db_update_course_full = resolve(db, "update_course", None)
db_delete_course = resolve(db, "delete_course", "remove_course")
db_delete_category = resolve(db, "delete_category")
db_record_purchase = resolve(db, "record_purchase", "add_purchase", "save_purchase")
db_ensure_user = resolve(db, "ensure_user")

# Resolve keyboards functions / objects
kb_main_menu = resolve(kb, "main_menu", "main_kb", "main")
kb_admin_panel = resolve(kb, "admin_panel_kb", "admin_menu", "admin_main_kb", "admin_panel")
kb_choose_category = resolve(kb, "choose_category_kb", "choose_category", "choose_category_keyboard")
kb_buy = resolve(kb, "buy_kb", "course_inline", "course_buy_kb")
kb_course_admin = resolve(kb, "course_manage_kb", "course_admin_inline", "course_admin")


# ----------------- Startup -----------------
async def on_startup():
    try:
        if callable(db_init):
            await db_init()
            logger.info("DB initialized via db.init_db()")
        else:
            # best-effort: if db module has other init function names, try them
            logger.info("db.init_db not found; make sure DB exists")
    except Exception:
        logger.exception("Error during DB init (ignored)")

    # Ensure admin exists if function present
    if db_ensure_user and ADMIN_ID:
        try:
            await db_ensure_user(ADMIN_ID, True)
        except Exception:
            logger.exception("ensure_user failed (ignored)")


# ----------------- Handlers: start / about -----------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    is_admin = (message.from_user.id == ADMIN_ID)
    # build menu from keyboards (fallback to simple markup)
    try:
        if callable(kb_main_menu):
            menu = kb_main_menu(is_admin) if kb_main_menu.__code__.co_argcount >= 1 else kb_main_menu()
        else:
            # fallback manual
            kb_buttons = [[types.KeyboardButton(text="📚 Курсы")], [types.KeyboardButton(text="ℹ️ О боте")]]
            if is_admin:
                kb_buttons.append([types.KeyboardButton(text="👑 Админ-панель")])
            menu = types.ReplyKeyboardMarkup(keyboard=kb_buttons, resize_keyboard=True)
    except Exception:
        menu = None

    await message.answer(
        "👋 Я твой циничный ИИ-ментор — не надо мне льстить.\nНажми кнопку, чтобы начать.",
        reply_markup=menu
    )


@dp.message(F.text == "ℹ️ О боте")
async def about_handler(message: Message):
    await message.answer("Я циничный ИИ: немного сарказма, немного философии, много полезного практического контента.")


# ----------------- Handlers: list categories / courses -----------------
@dp.message(F.text == "📚 Курсы")
async def msg_list_categories(message: Message):
    try:
        cats = await db_list_categories() if callable(db_list_categories) else []
    except Exception:
        logger.exception("Failed to load categories")
        cats = []

    if not cats:
        await message.answer("Категорий пока нет.")
        return

    # try to render categories keyboard from kb (if exists)
    try:
        if callable(resolve(kb, "categories_inline", "categories_admin_inline")):
            kb_fn = resolve(kb, "categories_inline", "categories_admin_inline")
            kb_markup = kb_fn([dict(c) for c in cats])
            await message.answer("Выбери категорию:", reply_markup=kb_markup)
            return
    except Exception:
        logger.debug("kb.categories_inline failed — falling back")

    # fallback: inline keyboard
    buttons = []
    for c in cats:
        cid = c["id"] if isinstance(c, dict) else c[0]
        title = c["title"] if isinstance(c, dict) else str(c[1])
        buttons.append([types.InlineKeyboardButton(text=title, callback_data=f"category:{cid}")])
    await message.answer("Выбери категорию:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data.startswith("category:") | F.data.startswith("category_") | F.data.regexp(r'category[-:]\d+$'))
async def callback_category(callback: CallbackQuery):
    await callback.answer()
    cid = extract_id(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить категорию.")
        return

    try:
        courses = await (db_list_courses_by_category(cid) if callable(db_list_courses_by_category) else (db_list_courses() if callable(db_list_courses) else []))
    except Exception:
        logger.exception("Failed to get courses for category")
        courses = []

    if not courses:
        await callback.message.answer("В этой категории пока нет курсов.")
        return

    for c in courses:
        course = dict(c) if not isinstance(c, dict) else c
        text = f"<b>{course.get('title')}</b>\n\n{course.get('description','')}\n\nЦена: {course.get('price',0)} ₽"
        # try kb.buy (function that formats button)
        try:
            if callable(kb_buy):
                # some kb functions expect (price, id) or (course)
                try:
                    kb_markup = kb_buy(course)  # prefer passing course dict
                except Exception:
                    try:
                        kb_markup = kb_buy(course.get('price', 0), course['id'])
                    except Exception:
                        kb_markup = None
                if kb_markup:
                    await callback.message.answer(text, reply_markup=kb_markup)
                    continue
        except Exception:
            logger.debug("kb.buy failed — fallback to simple inline")

        # fallback inline buy button
        buy_btn = types.InlineKeyboardButton(text=f"💳 Оплатить — {course.get('price',0)} ₽", callback_data=f"buy:{course['id']}")
        await callback.message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[buy_btn]]))


# ----------------- Payment handlers -----------------
@dp.callback_query(F.data.startswith("buy:") | F.data.startswith("buy_") | F.data.regexp(r'buy[-:]\d+$'))
async def callback_buy(callback: CallbackQuery):
    await callback.answer()
    cid = extract_id(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить курс для оплаты.")
        return

    try:
        course = await db_get_course(cid) if callable(db_get_course) else None
    except Exception:
        logger.exception("Failed to load course for buy")
        course = None

    if not course:
        await callback.message.answer("Курс не найден.")
        return

    course = dict(course) if not isinstance(course, dict) else course
    price_rub = int(course.get("price", 0))

    if price_rub <= 0:
        await callback.message.answer("Неверная цена курса.")
        return

    if not PAYMENT_PROVIDER_TOKEN:
        await callback.message.answer("Платежная система не настроена. Обратитесь к админу.")
        return

    prices = [LabeledPrice(label=course.get("title", "Курс"), amount=price_rub * 100)]
    payload = f"course:{cid}"
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=course.get("title", "Курс"),
            description=course.get("description", "") or "",
            payload=payload,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter=f"buy_{cid}",
        )
    except Exception:
        logger.exception("send_invoice failed")
        await callback.message.answer("Ошибка отправки инвойса — проверьте PROVIDER_TOKEN.")


@dp.pre_checkout_query()
async def precheckout(q: PreCheckoutQuery):
    try:
        await bot.answer_pre_checkout_query(q.id, ok=True)
    except Exception:
        logger.exception("pre_checkout failed")


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    try:
        payload = message.successful_payment.invoice_payload or ""
        cid = None
        if payload.startswith("course:"):
            cid = int(payload.split(":",1)[1])
        # record purchase (if function available)
        if cid and callable(db_record_purchase):
            try:
                await db_record_purchase(message.from_user.id, cid)
            except Exception:
                logger.exception("record_purchase failed")
        # respond with course link if available
        if cid and callable(db_get_course):
            c = await db_get_course(cid)
            if c:
                c = dict(c) if not isinstance(c, dict) else c
                link = c.get("link")
                text = f"✅ Оплата принята. Курс «{c.get('title')}»"
                if link:
                    await message.answer(f"{text}\n\nСсылка: {link}")
                    return
        await message.answer("✅ Оплата принята. Ссылка будет отправлена при первой возможности.")
    except Exception:
        logger.exception("successful_payment handler error")
        await message.answer("Оплата принята — произошла внутренняя ошибка при обработке.")


# ----------------- Admin: panel, categories, courses CRUD -----------------
@dp.message(F.text.in_({"👑 Админ-панель", "⚙️ Админ панель", "⚙️ Админ", "Админ"}))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступно только администратору.")
        return
    # try to use admin keyboard
    try:
        kb_markup = kb_admin_panel() if callable(kb_admin_panel) else kb_admin_panel
    except Exception:
        kb_markup = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="📂 Управление курсами")],
                [types.KeyboardButton(text="📂 Управление категориями")],
                [types.KeyboardButton(text="➕ Добавить курс")],
                [types.KeyboardButton(text="➕ Добавить категорию")],
                [types.KeyboardButton(text="❌ Отмена")]
            ],
            resize_keyboard=True
        )
    await message.answer("Панель администратора:", reply_markup=kb_markup)


# Admin: add category (callback or message)
@dp.message(F.text == "➕ Добавить категорию")
async def admin_add_category_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddCategory.waiting_for_title)
    await message.answer("Введите название новой категории:", reply_markup=kb.choose_category_kb([]) if callable(kb_choose_category) else None)


@dp.message(StateFilter(AddCategory.waiting_for_title))
async def admin_add_category_finish(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    if callable(db_add_category):
        await db_add_category(message.text)
        await state.clear()
        await message.answer("Категория добавлена.")
    else:
        await state.clear()
        await message.answer("DB: add_category не реализована.")


# Admin: list/manage courses
@dp.message(F.text == "📂 Управление курсами")
async def admin_manage_courses(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        courses = await (db_list_courses() if callable(db_list_courses) else [])
    except Exception:
        logger.exception("list courses failed")
        courses = []
    if not courses:
        await message.answer("Курсов пока нет.")
        return
    # try to use admin inline keyboard
    try:
        admin_courses_kb = resolve(kb, "admin_courses_inline", "admin_courses", "admin_courses_kb")
        if callable(admin_courses_kb):
            await message.answer("Список курсов:", reply_markup=admin_courses_kb([dict(c) for c in courses]))
            return
    except Exception:
        logger.debug("kb.admin_courses_inline failed")
    # fallback: list with inline per-course manage button
    for c in courses:
        course = dict(c) if not isinstance(c, dict) else c
        text = f"<b>{course.get('title')}</b>\n{course.get('description','')}\nЦена: {course.get('price')} ₽"
        # build manage inline
        manage = None
        try:
            if callable(kb_course_admin):
                manage = kb_course_admin(course['id'])
        except Exception:
            manage = None
        if not manage:
            manage = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{course['id']}")],
                [types.InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete:{course['id']}")]
            ])
        await message.answer(text, reply_markup=manage)


@dp.callback_query(F.data.startswith("delete:") | F.data.startswith("delete_") | F.data.startswith("delete-course") | F.data.startswith("delete_course:") )
async def admin_delete_course_cb(callback: CallbackQuery):
    await callback.answer()
    cid = extract_id(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить курс для удаления.")
        return
    if callable(db_delete_course):
        await db_delete_course(cid)
        await callback.message.answer("Курс удалён.")
    else:
        await callback.message.answer("DB: delete_course не реализован.")


@dp.callback_query(F.data.startswith("edit:") | F.data.startswith("edit_") | F.data.startswith("edit-course") | F.data.startswith("edit_course:"))
async def admin_edit_course_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    cid = extract_id(callback.data)
    if cid is None:
        await callback.message.answer("Не удалось определить курс.")
        return
    await state.update_data(course_id=cid)
    await state.set_state(EditCourse.waiting_for_new_title)
    await callback.message.answer("Введите новое название курса (или ❌ Отмена):")


@dp.message(StateFilter(EditCourse.waiting_for_new_title))
async def admin_edit_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    await state.update_data(new_title=message.text)
    await state.set_state(EditCourse.waiting_for_new_description)
    await message.answer("Введите новое описание:")


@dp.message(StateFilter(EditCourse.waiting_for_new_description))
async def admin_edit_description(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    await state.update_data(new_description=message.text)
    await state.set_state(EditCourse.waiting_for_new_price)
    await message.answer("Введите новую цену (в рублях):")


@dp.message(StateFilter(EditCourse.waiting_for_new_price))
async def admin_edit_price(message: Message, state: FSMContext):
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
async def admin_edit_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.")
        return
    data = await state.get_data()
    cid = data.get("course_id")
    # Prefer full update function
    try:
        if callable(db_update_course_full):
            await db_update_course_full(cid, data.get("new_title"), data.get("new_description"), data.get("new_price"), message.text)
        elif callable(db_update_course_field):
            await db_update_course_field(cid, "title", data.get("new_title"))
            await db_update_course_field(cid, "description", data.get("new_description"))
            await db_update_course_field(cid, "price", data.get("new_price"))
            await db_update_course_field(cid, "link", message.text)
        else:
            await message.answer("DB: no update function available.")
            await state.clear()
            return
        await state.clear()
        await message.answer("Курс обновлён.")
    except Exception:
        logger.exception("Failed to update course")
        await message.answer("Ошибка при обновлении курса.")
        await state.clear()


# Global cancel
@dp.message(F.text == "❌ Отмена")
async def cancel_global(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Операция отменена.")


# Fallback
@dp.message()
async def fallback(message: Message):
    await message.answer("Я не понял. Используй меню.")


# ----------------- Запуск -----------------
async def main():
    await on_startup()
    logger.info("Bot starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())





