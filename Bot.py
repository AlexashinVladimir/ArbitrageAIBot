# Bot.py — полный рабочий бот, aiogram 3.6 compatible
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
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery

import db
import keyboards as kb

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")  # leave empty if not configured

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set in .env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------- Bot & Dispatcher ----------
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ---------- FSM States (embedded to avoid extra file) ----------
class States:
    class AddCategory(StatesGroup):
        waiting_title = State()

    class EditCategory(StatesGroup):
        waiting_new_title = State()

    class AddCourse(StatesGroup):
        choosing_category = State()
        waiting_title = State()
        waiting_description = State()
        waiting_price = State()
        waiting_link = State()

    class EditCourse(StatesGroup):
        waiting_field_choice = State()
        waiting_new_value = State()


# ---------- Helpers ----------
def extract_int(s: str | None) -> int | None:
    if not s:
        return None
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def safe_reply_main(is_admin_flag: bool):
    try:
        return types.ReplyKeyboardMarkup(keyboard=[
            [types.KeyboardButton(text="📚 Курсы")],
            [types.KeyboardButton(text="ℹ️ О боте")] + ([] if not is_admin_flag else [])
        ], resize_keyboard=True)
    except Exception:
        return kb.reply_main_menu(is_admin_flag)


# ---------- Startup: ensure DB ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    try:
        await db.create_tables()
    except Exception:
        logger.exception("DB create_tables failed on start")
    await message.answer(
        "👋 Привет — я твой циничный ИИ-наставник. Что делаем?",
        reply_markup=kb.reply_main_menu(is_admin(message.from_user.id))
    )


# ---------- About ----------
@dp.message(F.text == "ℹ️ О боте")
async def about_handler(message: Message):
    await message.answer(
        "Я немного циничный ИИ с глубокой философией — помогаю людям становиться лучше, давая факты и практику."
    )


# ---------- User flow: categories -> courses list -> course detail -> buy ----------
@dp.message(F.text == "📚 Курсы")
async def user_categories(message: Message):
    cats = await db.get_categories()
    if not cats:
        await message.answer("Категорий пока нет.")
        return
    await message.answer("📂 Выберите категорию:", reply_markup=kb.categories_list(cats, for_add=False))


@dp.callback_query(F.data.startswith("catview:") | F.data.startswith("catview:".replace(":", ":")))
async def on_catview(callback: CallbackQuery):
    # support "catview:{id}"
    cid = extract_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка категории", show_alert=True)
        return
    courses = await db.get_courses_by_category(cid)
    if not courses:
        await callback.message.edit_text("В этой категории пока нет курсов.", reply_markup=kb.categories_list(await db.get_categories(), for_add=False))
        return
    await callback.message.edit_text("📚 Курсы в категории:", reply_markup=kb.courses_list(courses, category_id=cid))


@dp.callback_query(F.data.startswith("course:"))
async def on_course_selected(callback: CallbackQuery):
    cid = extract_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка курса", show_alert=True)
        return
    course = await db.get_course(cid)
    if not course:
        await callback.answer("Курс не найден", show_alert=True)
        return
    text = f"🚀 <b>{course['title']}</b>\n\n{course.get('description','')}"
    await callback.message.edit_text(text, reply_markup=kb.course_detail(course))


@dp.callback_query(F.data.startswith("buy:"))
async def on_buy(callback: CallbackQuery):
    cid = extract_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка покупки", show_alert=True)
        return
    course = await db.get_course(cid)
    if not course:
        await callback.answer("Курс не найден", show_alert=True)
        return
    price = int(course.get("price", 0) or 0)
    if price <= 0:
        await callback.answer("Неверная цена", show_alert=True)
        return
    if not PAYMENT_PROVIDER_TOKEN:
        await callback.answer("Платежи не настроены. Обратитесь к администратору.", show_alert=True)
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
        await callback.message.answer("Не удалось отправить инвойс — проверьте PAYMENT_PROVIDER_TOKEN.")


@dp.pre_checkout_query()
async def precheckout(query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def on_successful_payment(message: Message):
    payload = (message.successful_payment and message.successful_payment.invoice_payload) or ""
    cid = extract_int(payload)
    if cid is None:
        await message.answer("Оплата принята, но не удалось сопоставить курс.")
        return
    course = await db.get_course(cid)
    if not course:
        await message.answer("Оплата принята, курс не найден.")
        return
    link = course.get("link") or ""
    if link:
        await message.answer(f"✅ Оплата прошла — вот ссылка на курс:\n{link}")
    else:
        await message.answer("✅ Оплата прошла — но ссылка не установлена. Свяжитесь с админом.")


# ---------- Admin panel entry ----------
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    await message.answer("⚙️ Админ-панель:", reply_markup=kb.reply_admin_menu())


# ---------- Admin: Categories CRUD ----------
@dp.message(F.text == "➕ Добавить категорию")
async def admin_add_category_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(States.AddCategory.waiting_title)
    await message.answer("Введите название новой категории (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(States.AddCategory.waiting_title))
async def admin_add_category_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.reply_admin_menu())
        return
    await db.add_category(message.text.strip())
    await state.clear()
    await message.answer("✅ Категория добавлена.", reply_markup=kb.reply_admin_menu())


@dp.message(F.text == "📂 Управление категориями" )
async def admin_manage_categories(message: Message):
    if not is_admin(message.from_user.id):
        return
    cats = await db.get_categories()
    if not cats:
        await message.answer("Категорий нет.", reply_markup=kb.reply_admin_menu())
        return
    await message.answer("Категории (редактирование/удаление):", reply_markup=kb.edit_delete_categories(cats))


@dp.callback_query(F.data.startswith("delete_category:"))
async def admin_delete_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка", show_alert=True)
        return
    await db.delete_category(cid)
    await callback.message.answer("Категория удалена.", reply_markup=kb.reply_admin_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_category:"))
async def admin_edit_category_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка", show_alert=True)
        return
    await state.update_data(edit_category_id=cid)
    await state.set_state(States.EditCategory.waiting_new_title)
    await callback.message.answer("Введите новое название категории (или ❌ Отмена):", reply_markup=kb.cancel_kb())
    await callback.answer()


@dp.message(StateFilter(States.EditCategory.waiting_new_title))
async def admin_edit_category_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.reply_admin_menu())
        return
    data = await state.get_data()
    cid = data.get("edit_category_id")
    if cid is None:
        await state.clear()
        await message.answer("Нет выбранной категории.", reply_markup=kb.reply_admin_menu())
        return
    await db.update_category(cid, message.text.strip())
    await state.clear()
    await message.answer("Категория обновлена.", reply_markup=kb.reply_admin_menu())


# ---------- Admin: Courses CRUD (add, list, edit, delete) ----------
@dp.message(F.text == "➕ Добавить курс")
async def admin_add_course_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    cats = await db.get_categories()
    if not cats:
        await message.answer("Сначала добавьте категорию.", reply_markup=kb.reply_admin_menu())
        return
    await state.set_state(States.AddCourse.choosing_category)
    await message.answer("Выберите категорию для нового курса:", reply_markup=kb.categories_list(cats, for_add=True))


@dp.callback_query(StateFilter(States.AddCourse.choosing_category), F.data.startswith("catadd:"))
async def admin_choose_category_for_course(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка", show_alert=True)
        return
    await state.update_data(category_id=cid)
    await state.set_state(States.AddCourse.waiting_title)
    await callback.message.answer("Введите название курса (или ❌ Отмена):", reply_markup=kb.cancel_kb())
    await callback.answer()


@dp.message(StateFilter(States.AddCourse.waiting_title))
async def admin_add_course_title(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.reply_admin_menu())
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(States.AddCourse.waiting_description)
    await message.answer("Введите описание курса (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(States.AddCourse.waiting_description))
async def admin_add_course_description(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.reply_admin_menu())
        return
    await state.update_data(description=message.text.strip())
    await state.set_state(States.AddCourse.waiting_price)
    await message.answer("Введите цену курса в рублях (целое число) (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(States.AddCourse.waiting_price))
async def admin_add_course_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.reply_admin_menu())
        return
    if not message.text.isdigit():
        await message.answer("Цена должна быть целым числом. Попробуйте ещё раз.")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(States.AddCourse.waiting_link)
    await message.answer("Вставьте ссылку на курс (или ❌ Отмена):", reply_markup=kb.cancel_kb())


@dp.message(StateFilter(States.AddCourse.waiting_link))
async def admin_add_course_link(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.reply_admin_menu())
        return
    data = await state.get_data()
    c_id = data.get("category_id")
    title = data.get("title")
    description = data.get("description")
    price = data.get("price")
    link = message.text.strip()
    if None in (c_id, title, description, price):
        await state.clear()
        await message.answer("Недостаточно данных — операция отменена.", reply_markup=kb.reply_admin_menu())
        return
    await db.add_course(c_id, title, description, price, link)
    await state.clear()
    await message.answer("Курс создан.", reply_markup=kb.reply_admin_menu())


@dp.message(F.text == "📘 Управление курсами")
async def admin_manage_courses(message: Message):
    if not is_admin(message.from_user.id):
        return
    courses = await db.get_all_courses()
    if not courses:
        await message.answer("Курсов нет.", reply_markup=kb.reply_admin_menu())
        return
    await message.answer("Курсы (редактирование/удаление):", reply_markup=kb.edit_delete_courses(courses))


@dp.callback_query(F.data.startswith("delete_course:"))
async def admin_delete_course(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка", show_alert=True)
        return
    await db.delete_course(cid)
    await callback.message.answer("Курс удалён.", reply_markup=kb.reply_admin_menu())
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_course:"))
async def admin_edit_course_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    cid = extract_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка", show_alert=True)
        return
    await state.update_data(edit_course_id=cid)
    await state.set_state(States.EditCourse.waiting_field_choice)
    await callback.message.answer("Выберите поле для редактирования:", reply_markup=kb.edit_course_fields(cid))
    await callback.answer()


@dp.callback_query(F.data.regexp(r"^edit_course_field:(title|description|price|link):\d+$"))
async def admin_edit_course_field(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    parts = callback.data.split(":")
    field = parts[1]
    cid = int(parts[2])
    await state.update_data(edit_course_id=cid, edit_field=field)
    await state.set_state(States.EditCourse.waiting_new_value)
    await callback.message.answer(f"Введи новое значение для <b>{field}</b> (или ❌ Отмена):", reply_markup=kb.cancel_kb())
    await callback.answer()


@dp.message(StateFilter(States.EditCourse.waiting_new_value))
async def admin_save_edited_course_value(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.reply_admin_menu())
        return
    data = await state.get_data()
    cid = data.get("edit_course_id")
    field = data.get("edit_field")
    if cid is None or not field:
        await state.clear()
        await message.answer("Нет данных для редактирования.", reply_markup=kb.reply_admin_menu())
        return
    val = message.text.strip()
    if field == "price":
        if not val.isdigit():
            await message.answer("Цена должна быть числом.")
            return
        val = int(val)
    await db.update_course_field(cid, field, val)
    await state.clear()
    await message.answer("Курс обновлён.", reply_markup=kb.reply_admin_menu())


# ---------- Back / Cancel handlers ----------
@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("Главное меню:", reply_markup=kb.reply_main_menu(is_admin(callback.from_user.id)))


@dp.callback_query(F.data == "back_admin")
async def back_admin(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("Админ-панель:", reply_markup=kb.reply_admin_menu())


@dp.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    await callback.answer()
    cats = await db.get_categories()
    await callback.message.edit_text("Категории:", reply_markup=kb.categories_list(cats, for_add=False))


@dp.callback_query(F.data.startswith("back_to_category:"))
async def back_to_category(callback: CallbackQuery):
    await callback.answer()
    cid = extract_int(callback.data)
    if cid is None:
        await callback.answer("Ошибка", show_alert=True)
        return
    courses = await db.get_courses_by_category(cid)
    await callback.message.edit_text("Курсы в категории:", reply_markup=kb.courses_list(courses, category_id=cid))


@dp.message(F.text == "⬅️ Назад")
async def reply_back(message: Message):
    await message.answer("Главное меню:", reply_markup=kb.reply_main_menu(is_admin(message.from_user.id)))


@dp.message(F.text == "❌ Отмена")
async def reply_cancel(message: Message, state: FSMContext):
    await state.clear()
    if is_admin(message.from_user.id):
        await message.answer("Отменено.", reply_markup=kb.reply_admin_menu())
    else:
        await message.answer("Отменено.", reply_markup=kb.reply_main_menu(is_admin(message.from_user.id)))


# Catch-all callback — убирает "not handled" spam
@dp.callback_query()
async def catch_all(cb: CallbackQuery):
    logger.debug("Unhandled callback: %s from %s", cb.data, cb.from_user.id)
    await cb.answer()

# ---------- Run ----------
async def main():
    try:
        await db.create_tables()
    except Exception:
        logger.exception("DB create_tables failed at startup")
    logger.info("Bot starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())



