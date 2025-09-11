# Bot.py — основной файл бота (Aiogram 3.6)
import asyncio
import logging
import os

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import LabeledPrice, PreCheckoutQuery

# Локальные модули (буду присылать по одному файлу; рядом с Bot.py)
import db
import keyboards as kb
import texts
from states import AddCategory, AddCourse, EditCourse

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфиг из .env
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в .env")

PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
if not PAYMENT_PROVIDER_TOKEN:
    # Бот может работать и без платежей, но если ты хочешь оплату — установи PAYMENT_PROVIDER_TOKEN.
    logger.warning("PAYMENT_PROVIDER_TOKEN не найден в .env — платежи будут неработоспособны.")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Бот и диспетчер
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ---------------------------
# Startup
# ---------------------------
async def on_startup():
    await db.init_db()  # создаст таблицы, если их нет
    # при необходимости — зарегистрировать админа в users (если реализовано в db)
    if ADMIN_ID:
        try:
            await db.ensure_user(ADMIN_ID, is_admin=True)
        except Exception:
            # если в db нет ensure_user — ок
            pass
    logger.info("Startup finished.")


# ---------------------------
# /start
# ---------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    is_admin = (message.from_user.id == ADMIN_ID)
    # Если есть texts.random_start(), используем его; иначе краткое сообщение
    try:
        text = texts.random_start()
    except Exception:
        text = "Привет. Выбирай — или оставайся прежним."
    await message.answer(text, reply_markup=kb.main_menu(is_admin))


# ---------------------------
# О боте
# ---------------------------
@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: types.Message):
    try:
        await message.answer(texts.random_about())
    except Exception:
        await message.answer("Я — циничный ИИ. Помогаю стать лучше — если хочешь.")


# ---------------------------
# Пользователь: просмотр категорий -> курсы
# ---------------------------
@dp.message(F.text == "📚 Курсы")
async def cmd_courses(message: types.Message):
    categories = await db.list_categories()
    if not categories:
        await message.answer(texts.CATEGORY_EMPTY if hasattr(texts, "CATEGORY_EMPTY") else "Категорий пока нет.")
        return
    await message.answer("Выбери категорию:", reply_markup=kb.categories_inline(categories))


@dp.callback_query(F.data.startswith("category:"))
async def category_cb(callback: types.CallbackQuery):
    await callback.answer()
    cat_id = int(callback.data.split(":", 1)[1])
    courses = await db.list_courses_by_category(cat_id)
    if not courses:
        await callback.message.answer(texts.COURSE_EMPTY if hasattr(texts, "COURSE_EMPTY") else "Курсов нет.")
        return

    for c in courses:
        course = dict(c) if not isinstance(c, dict) else c
        text = (
            f"<b>{course.get('title')}</b>\n\n"
            f"{course.get('description','')}\n\n"
            f"Цена: {course.get('price', 0)} ₽"
        )
        # передаём весь объект course, чтобы клавиатура показывала цену
        await callback.message.answer(text, reply_markup=kb.course_inline(course))


# ---------------------------
# Покупка: одна кнопка с ценой -> инвойс
# ---------------------------
@dp.callback_query(F.data.startswith("buy:"))
async def buy_cb(callback: types.CallbackQuery):
    await callback.answer()
    course_id = int(callback.data.split(":", 1)[1])
    course = await db.get_course(course_id)
    if not course:
        await callback.message.answer("Курс не найден.")
        return

    course = dict(course) if not isinstance(course, dict) else course

    if not PAYMENT_PROVIDER_TOKEN:
        await callback.message.answer("Платежная система не настроена. Обратитесь к администратору.")
        return

    # Цена в рублях (целое число), нужно передать в копейках
    amount_rub = int(course.get("price", 0))
    labeled_price = [LabeledPrice(label=course.get("title", "Курс"), amount=amount_rub * 100)]

    invoice_payload = f"course:{course_id}"

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=course.get("title", "Курс"),
        description=course.get("description", ""),
        payload=invoice_payload,
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=labeled_price,
        start_parameter=f"buy_{course_id}"
    )


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    pay = message.successful_payment
    payload = pay.invoice_payload or ""
    # Ожидаем payload вида "course:<id>"
    course_id = None
    if payload.startswith("course:"):
        try:
            course_id = int(payload.split(":", 1)[1])
        except Exception:
            course_id = None

    # Сохраняем покупку (если реализовано)
    try:
        if course_id is not None:
            await db.record_purchase(message.from_user.id, course_id)
    except Exception:
        # если db.record_purchase не реализовано — пропускаем
        pass

    # Ответ пользователю с ссылкой (если есть)
    course = None
    if course_id is not None:
        course = await db.get_course(course_id)
        if course:
            link = course.get("link") if isinstance(course, dict) else (dict(course).get("link") if course else None)
            # используем тексты.random_payment_success, если есть
            try:
                text = texts.random_payment_success(course['title'])
            except Exception:
                text = f"Оплата принята. Курс «{course['title']}» доступен."
            if link:
                await message.answer(f"{text}\n\nСсылка: {link}")
                return

    # fallback
    await message.answer("Оплата принята. Ссылка к курсу будет выдана администратором, если её нет в БД.")


# ---------------------------
# Админка: панель (в главное меню показывается кнопка админа)
# ---------------------------
@dp.message(F.text == "👑 Админ-панель")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY if hasattr(texts, "ADMIN_ONLY") else "Доступ запрещён.")
        return
    await message.answer("Админ-панель:", reply_markup=kb.admin_menu)


# ---------------------------
# Админ: категории (add/delete)
# ---------------------------
@dp.message(F.text == "Управление категориями")
async def admin_manage_categories(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY if hasattr(texts, "ADMIN_ONLY") else "Доступ запрещён.")
        return
    cats = await db.list_categories()
    await message.answer("Управление категориями:", reply_markup=kb.categories_admin_inline(cats))


@dp.callback_query(F.data == "admin_add_category")
async def cb_admin_add_category(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Введите название новой категории:", reply_markup=kb.cancel_kb)
    await state.set_state(AddCategory.waiting_for_title)


@dp.message(StateFilter(AddCategory.waiting_for_title))
async def admin_add_category_finish(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCELLED if hasattr(texts, "CANCELLED") else "Отменено.", reply_markup=kb.admin_menu)
        return
    await db.add_category(message.text)
    await state.clear()
    await message.answer("Категория добавлена.", reply_markup=kb.admin_menu)


@dp.callback_query(F.data.startswith("delcat:"))
async def cb_admin_del_category(callback: types.CallbackQuery):
    await callback.answer()
    cat_id = int(callback.data.split(":", 1)[1])
    await db.delete_category(cat_id)
    await callback.message.answer("Категория удалена.", reply_markup=kb.admin_menu)


# ---------------------------
# Админ: управление курсами (add / view list)
# ---------------------------
@dp.message(F.text == "Управление курсами")
async def admin_manage_courses(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY if hasattr(texts, "ADMIN_ONLY") else "Доступ запрещён.")
        return
    courses = await db.list_courses()
    await message.answer("Управление курсами:", reply_markup=kb.admin_courses_inline(courses))


@dp.callback_query(F.data == "admin_add_course")
async def cb_admin_add_course(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    cats = await db.list_categories()
    if not cats:
        await callback.message.answer("Сначала добавьте категорию.")
        return

    # показываем reply keyboard с названиями категорий
    await state.update_data(categories=[dict(c) for c in cats])
    buttons = [[types.KeyboardButton(text=c["title"])] for c in cats]
    buttons.append([types.KeyboardButton(text="❌ Отмена")])
    kb_reply = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await callback.message.answer("Выберите категорию для нового курса:", reply_markup=kb_reply)
    await state.set_state(AddCourse.waiting_for_category)


@dp.message(StateFilter(AddCourse.waiting_for_category))
async def admin_add_course_category(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление отменено.", reply_markup=kb.admin_menu)
        return

    data = await state.get_data()
    cats = data.get("categories", [])
    chosen = next((c for c in cats if c["title"] == message.text), None)
    if not chosen:
        await message.answer("Выберите категорию кнопкой.")
        return

    await state.update_data(category_id=chosen["id"])
    await state.set_state(AddCourse.waiting_for_title)
    await message.answer("Введите название курса:", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(AddCourse.waiting_for_title))
async def admin_add_course_title(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление отменено.", reply_markup=kb.admin_menu)
        return
    await state.update_data(title=message.text)
    await state.set_state(AddCourse.waiting_for_description)
    await message.answer("Введите описание курса:", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(AddCourse.waiting_for_description))
async def admin_add_course_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление отменено.", reply_markup=kb.admin_menu)
        return
    await state.update_data(description=message.text)
    await state.set_state(AddCourse.waiting_for_price)
    await message.answer("Введите цену курса (в рублях):", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(AddCourse.waiting_for_price))
async def admin_add_course_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление отменено.", reply_markup=kb.admin_menu)
        return
    if not message.text.isdigit():
        await message.answer("Цена должна быть числом.")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddCourse.waiting_for_link)
    await message.answer("Введите ссылку на курс (URL или текст):", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(AddCourse.waiting_for_link))
async def admin_add_course_link(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Добавление отменено.", reply_markup=kb.admin_menu)
        return
    data = await state.get_data()
    await db.add_course(
        category_id=data["category_id"],
        title=data["title"],
        description=data["description"],
        price=data["price"],
        link=message.text
    )
    await state.clear()
    await message.answer("Курс добавлен.", reply_markup=kb.admin_menu)


# ---------------------------
# Админ: редактирование / удаление курса
# ---------------------------
@dp.callback_query(F.data.startswith("admin_course:"))
async def admin_course_view(callback: types.CallbackQuery):
    await callback.answer()
    course_id = int(callback.data.split(":", 1)[1])
    course = await db.get_course(course_id)
    if not course:
        await callback.message.answer("Курс не найден.")
        return
    course = dict(course) if not isinstance(course, dict) else course
    text = (
        f"<b>{course.get('title')}</b>\n\n"
        f"{course.get('description','')}\n\n"
        f"Цена: {course.get('price', 0)} ₽\n"
        f"Ссылка: {course.get('link','-')}"
    )
    await callback.message.answer(text, reply_markup=kb.course_admin_inline(course_id))


@dp.callback_query(F.data.startswith("delcourse:"))
async def admin_delete_course(callback: types.CallbackQuery):
    await callback.answer()
    course_id = int(callback.data.split(":", 1)[1])
    await db.delete_course(course_id)
    await callback.message.answer("Курс удалён.", reply_markup=kb.admin_menu)


@dp.callback_query(F.data.startswith("editcourse:"))
async def admin_edit_course_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    course_id = int(callback.data.split(":", 1)[1])
    await state.update_data(course_id=course_id)
    await state.set_state(EditCourse.waiting_for_field)
    await callback.message.answer("Что редактируем?", reply_markup=kb.edit_course_kb)


@dp.message(StateFilter(EditCourse.waiting_for_field))
async def admin_edit_course_field(message: types.Message, state: FSMContext):
    mapping = {"Название": "title", "Описание": "description", "Цена": "price", "Ссылка": "link"}
    if message.text not in mapping:
        await message.answer("Выберите поле кнопкой.")
        return
    await state.update_data(field=mapping[message.text])
    await state.set_state(EditCourse.waiting_for_value)
    await message.answer(f"Введите новое значение для «{message.text}»: (или ❌ Отмена)", reply_markup=kb.cancel_kb)


@dp.message(StateFilter(EditCourse.waiting_for_value))
async def admin_edit_course_value(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Редактирование отменено.", reply_markup=kb.admin_menu)
        return
    data = await state.get_data()
    course_id = data.get("course_id")
    field = data.get("field")
    value = message.text
    if field == "price":
        if not value.isdigit():
            await message.answer("Цена должна быть числом.")
            return
        value = int(value)
    await db.update_course_field(course_id, field, value)
    await state.clear()
    await message.answer("Курс обновлён.", reply_markup=kb.admin_menu)


# ---------------------------
# Отмена по кнопке "❌ Отмена" (глобально)
# ---------------------------
@dp.message(F.text == "❌ Отмена")
async def cancel_any(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.CANCELLED if hasattr(texts, "CANCELLED") else "Отменено.", reply_markup=kb.main_menu(message.from_user.id == ADMIN_ID))


# ---------------------------
# Фолбэк
# ---------------------------
@dp.message()
async def fallback(message: types.Message):
    try:
        txt = texts.random_fallback()
    except Exception:
        txt = "Не понял. Используй главное меню."
    await message.answer(txt, reply_markup=kb.main_menu(message.from_user.id == ADMIN_ID))


# ---------------------------
# Запуск
# ---------------------------
async def main():
    await on_startup()
    logger.info("Bot polling started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


