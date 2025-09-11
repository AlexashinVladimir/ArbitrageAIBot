# Bot.py — Aiogram 3.6 — полный рабочий файл
import asyncio
import logging
import os
from dotenv import load_dotenv

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

# ---------------- config & logging ----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN") or os.getenv("PAYMENTS_TOKEN") or os.getenv("PAYMENTS_PROVIDER_TOKEN") or ""
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot initialization (use DefaultBotProperties to avoid deprecation warning)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ---------------- States ----------------
class CatStates(StatesGroup):
    adding_title = State()
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


# ---------------- Helpers ----------------
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def extract_last_int(s: str) -> int | None:
    import re
    m = re.search(r"(\d+)(?!.*\d)", s)
    return int(m.group(1)) if m else None


# ---------------- Startup ----------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Start command — shows main menu (admin sees admin button)."""
    admin = is_admin(message.from_user.id)
    await db.create_tables()
    await message.answer(
        "Привет. Я циничный ИИ-ментор. Хочешь учиться или разбирать мир по косточкам?",
        reply_markup=kb.main_menu(admin),
    )


# ---------------- About ----------------
@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message):
    await message.answer("Немного сарказма, немного мудрости. Я помогаю стать лучшей версией себя — или хотя бы попытаться.")


# ---------------- Show categories -> courses flow ----------------
@dp.message(F.text == "📚 Курсы")
async def show_categories(message: Message):
    cats = await db.get_categories()
    if not cats:
        await message.answer("Пока нет ни одной категории.")
        return
    # keyboards.categories_inline expects list[dict] with 'id' and 'title'/'name'
    # adapt if db returns 'name'
    adapted = []
    for c in cats:
        if isinstance(c, dict):
            # accept either 'title' or 'name'
            title = c.get("title") or c.get("name") or c.get("title_en") or str(c.get("id"))
            adapted.append({"id": c["id"], "title": title})
        else:
            # tuple fallback (id, title)
            adapted.append({"id": c[0], "title": c[1]})
    try:
        markup = kb.categories_inline(adapted)
    except Exception:
        # fallback build
        markup = InlineKeyboardMarkup()
        for c in adapted:
            markup.add(InlineKeyboardButton(text=c["title"], callback_data=f"category_{c['id']}"))
    await message.answer("Выбирай категорию:", reply_markup=markup)


@dp.callback_query(F.data.startswith("category_"))
async def on_category_click(callback: CallbackQuery):
    cid = extract_last_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка категории.", show_alert=True)
        return
    courses = await db.get_courses(cid)
    if not courses:
        await callback.message.answer("В этой категории пока нет курсов.")
        await callback.answer()
        return

    # adapt courses to dict with id,title,description,price,link
    adapted = []
    for r in courses:
        if isinstance(r, dict):
            adapted.append(r)
        else:
            # fallback for tuple rows
            # try to map (id, title, description, price, link)
            adapted.append({"id": r[0], "title": r[1], "description": r[2] if len(r) > 2 else "", "price": r[3] if len(r) > 3 else 0, "link": r[4] if len(r) > 4 else ""})

    # send each course: text (title + description), buy button (price on button)
    for course in adapted:
        title = course.get("title") or "Курс"
        desc = course.get("description") or ""
        text = f"<b>{title}</b>\n\n{desc}"
        try:
            buy_markup = kb.courses_inline([course])  # some kb expects list
        except Exception:
            buy_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 Купить ({int(course.get('price',0))} ₽)", callback_data=f"buy_{course['id']}")]
            ])
        await callback.message.answer(text, reply_markup=buy_markup)
    await callback.answer()


# ---------------- Payments ----------------
@dp.callback_query(F.data.startswith("buy_"))
async def on_buy_click(callback: CallbackQuery):
    cid = extract_last_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка покупки.", show_alert=True)
        return
    course = await db.get_course(cid)
    if not course:
        await callback.answer("Курс не найден.", show_alert=True)
        return
    price = int(course.get("price", 0))
    if price <= 0:
        await callback.answer("Неверная цена.", show_alert=True)
        return
    if not PAYMENT_PROVIDER_TOKEN:
        await callback.answer("Платежная система не настроена.", show_alert=True)
        return

    prices = [LabeledPrice(label=course.get("title", "Курс"), amount=price * 100)]
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=course.get("title", "Курс"),
            description=(course.get("description") or "")[:1000],
            payload=f"course_{cid}",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=prices,
            start_parameter=f"course_{cid}"
        )
    except Exception as e:
        logger.exception("send_invoice failed")
        await callback.answer("Ошибка отправки инвойса. Проверь платежный токен.", show_alert=True)
        return
    await callback.answer()


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload or ""
    cid = extract_last_int(payload)
    if cid is None:
        await message.answer("Оплата принята, но не смог найти курс.")
        return
    course = await db.get_course(cid)
    if not course:
        await message.answer("Оплата принята, но курс не найден.")
        return
    # send link
    link = course.get("link") or course.get("url") or ""
    if link:
        await message.answer(f"Оплата принята. Вот ваша ссылка:\n{link}")
    else:
        await message.answer("Оплата принята. Ссылка не найдена — свяжитесь с админом.")


# ---------------- Admin panel ----------------
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        await message.answer("Панель администратора:", reply_markup=kb.admin_menu())
    except Exception:
        # fallback keyboard
        kb_f = types.ReplyKeyboardMarkup(keyboard=[
            [types.KeyboardButton(text="➕ Добавить категорию")],
            [types.KeyboardButton(text="➕ Добавить курс")],
            [types.KeyboardButton(text="📂 Управление категориями")],
            [types.KeyboardButton(text="📘 Управление курсами")],
            [types.KeyboardButton(text="❌ Отмена")]
        ], resize_keyboard=True)
        await message.answer("Панель администратора:", reply_markup=kb_f)


# ----- Categories management ----- 
@dp.message(F.text == "📂 Управление категориями")
async def manage_categories(message: Message):
    if not is_admin(message.from_user.id):
        return
    cats = await db.get_categories()
    adapted = [{"id": c["id"], "title": c.get("title") or c.get("name") or c.get("title", "")} for c in cats]
    if not adapted:
        await message.answer("Нет категорий.")
        return
    # show edit/delete inline
    try:
        kb_inline = kb.edit_delete_inline("category", adapted)
    except Exception:
        kb_inline = InlineKeyboardMarkup()
        for c in adapted:
            kb_inline.add(
                InlineKeyboardButton(text=f"✏️ {c['title']}", callback_data=f"edit_category_{c['id']}"),
                InlineKeyboardButton(text=f"🗑 {c['title']}", callback_data=f"delete_category_{c['id']}")
            )
    await message.answer("Категории:", reply_markup=kb_inline)


@dp.callback_query(F.data.startswith("delete_category_"))
async def delete_category_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cid = extract_last_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка.", show_alert=True)
        return
    await db.delete_category(cid)
    await callback.message.answer("Категория удалена.")
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_category_"))
async def edit_category_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    cid = extract_last_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка.", show_alert=True)
        return
    await state.update_data(edit_cat_id=cid)
    await state.set_state(CatStates.editing_title)
    await callback.message.answer("Введи новое название категории (или ❌ Отмена):", reply_markup=kb.cancel_kb())
    await callback.answer()


@dp.message(StateFilter(CatStates.editing_title))
async def save_edited_category(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu())
        return
    data = await state.get_data()
    cid = data.get("edit_cat_id")
    if cid is None:
        await message.answer("Нет выбранной категории.")
        await state.clear()
        return
    # update category — db might not have update function, so do delete+add or implement update if exists
    # we will attempt to find update_category function; if not, perform simple update SQL via db module if available.
    if hasattr(db, "update_category"):
        await db.update_category(cid, message.text)
    else:
        # fallback: delete and add new (keeping id continuity is better with update; if not available, we simply add new)
        await db.delete_category(cid)
        await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория обновлена.", reply_markup=kb.admin_menu())


@dp.message(F.text == "➕ Добавить категорию")
async def add_category_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(CatStates.adding_title)
    await message.answer("Введи название новой категории (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(CatStates.adding_title))
async def add_category_finish(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отмена.", reply_markup=kb.admin_menu())
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена.", reply_markup=kb.admin_menu())


# ----- Courses management ----- 
@dp.message(F.text == "📘 Управление курсами")
async def manage_courses(message: Message):
    if not is_admin(message.from_user.id):
        return
    # gather courses across categories
    cats = await db.get_categories()
    courses_all = []
    for c in cats:
        cs = await db.get_courses(c["id"])
        for course in cs:
            courses_all.append(course)
    if not courses_all:
        await message.answer("Курсов нет.")
        return
    adapted = [{"id": c["id"], "title": c.get("title") or c.get("name") or ""} for c in courses_all]
    try:
        kb_inline = kb.edit_delete_inline("course", adapted)
    except Exception:
        kb_inline = InlineKeyboardMarkup()
        for c in adapted:
            kb_inline.add(
                InlineKeyboardButton(text=f"✏️ {c['title']}", callback_data=f"edit_course_{c['id']}"),
                InlineKeyboardButton(text=f"🗑 {c['title']}", callback_data=f"delete_course_{c['id']}")
            )
    await message.answer("Курсы:", reply_markup=kb_inline)


@dp.callback_query(F.data.startswith("delete_course_"))
async def delete_course_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    cid = extract_last_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка.", show_alert=True)
        return
    await db.delete_course(cid)
    await callback.message.answer("Курс удалён.")
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_course_"))
async def edit_course_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    cid = extract_last_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка.", show_alert=True)
        return
    # save course id and ask which field
    await state.update_data(edit_course_id=cid)
    await state.set_state(CourseStates.editing_field)
    # build inline asking which field to edit
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data=f"edit_field_name_{cid}")],
        [InlineKeyboardButton(text="Описание", callback_data=f"edit_field_description_{cid}")],
        [InlineKeyboardButton(text="Цена", callback_data=f"edit_field_price_{cid}")],
        [InlineKeyboardButton(text="Ссылка", callback_data=f"edit_field_link_{cid}")],
    ])
    await callback.message.answer("Что редактируем?", reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.regexp(r'^edit_field_(name|description|price|link)_[0-9]+$'))
async def edit_field_chosen(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    # extract field and id
    parts = callback.data.split("_")
    # format: ["edit","field","<field>","<id>"]
    field = parts[2]
    cid = int(parts[3])
    await state.update_data(edit_course_id=cid, edit_field=field)
    await state.set_state(CourseStates.editing_value)
    await callback.message.answer(f"Введи новое значение для {field} (или ❌ Отмена):", reply_markup=kb.cancel_kb())
    await callback.answer()


@dp.message(StateFilter(CourseStates.editing_value))
async def edit_course_save_value(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
        return
    data = await state.get_data()
    cid = data.get("edit_course_id")
    field = data.get("edit_field")
    if cid is None or field is None:
        await message.answer("Нет данных для редактирования.")
        await state.clear()
        return
    # attempt to use db.update_course if exists
    if hasattr(db, "update_course"):
        # update_course(id, title, description, price, link) — we need to fetch existing and replace field
        cur = await db.get_course(cid)
        if not cur:
            await message.answer("Курс не найден.")
            await state.clear()
            return
        title = cur.get("title")
        description = cur.get("description")
        price = cur.get("price")
        link = cur.get("link")
        if field == "name" or field == "title":
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
        try:
            await db.update_course(cid, title, description, price, link)
        except Exception:
            logger.exception("update_course failed")
            await message.answer("Ошибка при обновлении курса.")
            await state.clear()
            return
    elif hasattr(db, "update_course_field"):
        # update_course_field(id, field, value)
        await db.update_course_field(cid, field, message.text)
    else:
        # fallback: delete + re-add is unsafe, so inform admin
        await message.answer("Функция обновления курса не реализована в db.py.")
        await state.clear()
        return

    await state.clear()
    await message.answer("Курс обновлён.", reply_markup=kb.admin_menu())


# ---------------- Cancel global ----------------
@dp.message(F.text == "❌ Отмена")
async def cancel_global(message: Message, state: FSMContext):
    await state.clear()
    # show admin menu to admins, main menu to users
    if is_admin(message.from_user.id):
        await message.answer("Отменено.", reply_markup=kb.admin_menu())
    else:
        await message.answer("Отменено.", reply_markup=kb.main_menu(False))


# ---------------- Debug fallback callback (shows unseen callbacks) ----------------
@dp.callback_query()
async def debug_all_callbacks(cb: CallbackQuery):
    # log unseen callback data for diagnosis; don't interrupt other handlers
    logger.debug("Unhandled callback data: %s from %s", cb.data, cb.from_user.id)
    # always answer to remove the client 'loading' indicator
    await cb.answer()


# ---------------- Run ----------------
async def main():
    await db.create_tables()
    logger.info("Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())



