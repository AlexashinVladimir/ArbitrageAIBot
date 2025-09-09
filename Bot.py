"""
Bot.py — основной файл бота.
Поддержка: Aiogram 3.6+, SQLite (через aiosqlite), Polling, Telegram Payments.
Функционал редактирования курсов: название, описание, цена.
Запуск: python Bot.py
"""

import asyncio
import logging
import os
import secrets
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
import aiosqlite

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, Text
from aiogram.types import LabeledPrice, PreCheckoutQuery, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# Модули проекта (файлы должны существовать: db.py, keyboards.py, texts.py, states.py)
import db
import keyboards as kb
import texts
from states import AddCategory, AddCourse, EditCourse

# Загрузка окружения
load_dotenv()
TOKEN = os.getenv('TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
PAYMENT_PROVIDER_TOKEN = os.getenv('PAYMENT_PROVIDER_TOKEN')
CURRENCY = os.getenv('CURRENCY', 'RUB')
DB_PATH = os.getenv('DB_PATH', 'data.db')

if not TOKEN:
    raise RuntimeError("TOKEN is not set in .env")

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота, диспетчера и памяти состояний
bot = Bot(token=TOKEN, parse_mode='HTML')
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# -------------------- Startup --------------------
async def on_startup():
    # Инициализация базы данных
    await db.init_db(DB_PATH)
    # Убедимся, что админ есть в таблице пользователей
    if ADMIN_ID:
        await db.ensure_user(ADMIN_ID, is_admin=True)
    logger.info("Startup completed.")


# -------------------- Команды / обработчики для пользователей --------------------
@dp.message.register(Command("start"))
async def cmd_start(message: types.Message):
    """Старт — регистрируем пользователя и показываем главное меню."""
    await db.ensure_user(message.from_user.id)
    await message.answer(texts.START, reply_markup=kb.main_menu())


@dp.message.register(Text("ℹ️ О боте"))
async def about_handler(message: types.Message):
    await message.answer(texts.ABOUT)


@dp.message.register(Text("📚 Курсы"))
async def show_categories(message: types.Message):
    """Показываем доступные (active) категории."""
    categories = await db.list_categories(active_only=True)
    if not categories:
        await message.answer(texts.CATEGORY_EMPTY)
        return
    # Inline-клавиатура с категориями
    await message.answer("Выберите категорию:", reply_markup=kb.categories_inline(categories))


@dp.callback_query.register(lambda c: c.data and c.data.startswith("category:"))
async def category_callback(callback: types.CallbackQuery):
    """Показать курсы в категории."""
    await callback.answer()
    cat_id = int(callback.data.split(":", 1)[1])
    courses = await db.list_courses_by_category(cat_id)
    if not courses:
        await callback.message.answer(texts.COURSE_EMPTY)
        return
    await callback.message.answer("Курсы в категории:", reply_markup=kb.courses_inline(courses))


@dp.callback_query.register(lambda c: c.data and c.data.startswith("course_show:"))
async def course_show_cb(cb: types.CallbackQuery):
    """Показ информации о курсе."""
    await cb.answer()
    course_id = int(cb.data.split(":", 1)[1])
    course = await db.get_course(course_id)
    if not course:
        await cb.message.answer("Курс не найден.")
        return
    text = f"<b>{course['title']}</b>\n{course['description'] or ''}\nЦена: {course['price'] / 100:.2f} {course['currency']}"
    await cb.message.answer(text, reply_markup=kb.course_detail_inline(course))


# -------------------- Оплата --------------------
@dp.callback_query.register(lambda c: c.data and c.data.startswith("course_pay:"))
async def course_pay_cb(cb: types.CallbackQuery):
    """Начало оплаты — отправка счета (invoice)."""
    await cb.answer()
    payload = cb.data.split(":", 1)[1]
    course = await db.get_course_by_payload(payload)
    if not course:
        await cb.message.answer("Курс не найден.")
        return

    title = course["title"]
    description = course["description"] or title

    # Сумма — в наименьших единицах (копейки для RUB)
    price_value = int(course["price"])
    labeled_price = [LabeledPrice(label=title, amount=price_value)]

    # Сформируем уникальный payload (сделаем привязку к id курса для простоты)
    invoice_payload = f"course_{course['id']}_{secrets.token_hex(6)}"

    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title=title,
        description=description,
        payload=invoice_payload,
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency=course["currency"],
        prices=labeled_price,
        start_parameter=f"buy_{course['id']}",
    )


@dp.pre_checkout_query.register()
async def pre_checkout(query: PreCheckoutQuery):
    """Подтверждение pre-checkout (всегда ОК в этом демо)."""
    await query.answer(ok=True)


@dp.message.register(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    """
    Обработка успешной оплаты.
    Сопоставляем курс по payload (в invoice.payload мы специально положили 'course_{id}_...').
    """
    pay = message.successful_payment
    payload = pay.invoice_payload
    course = None

    # Попытка достать id курса из payload
    if payload and payload.startswith("course_"):
        try:
            course_id = int(payload.split("_")[1])
            course = await db.get_course(course_id)
        except Exception:
            course = None

    # Если не получилось — попытаемся сопоставить по сумме и валюте (fallback)
    if not course:
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM courses")
            rows = await cur.fetchall()
            for r in rows:
                if int(r["price"]) == int(pay.total_amount) and r["currency"] == pay.currency:
                    course = dict(r)
                    break

    if not course:
        await message.answer("Платёж получен, но не удалось сопоставить курс. Свяжитесь с администратором.")
        return

    # Запись покупки в БД
    user_db_id = await db.ensure_user(message.from_user.id)
    await db.record_purchase(user_db_id, course["id"], datetime.utcnow().isoformat(), payload)

    # Отправим доступ (в демо — просто описание)
    await message.answer(texts.COURSE_PURCHASED.format(title=course["title"]))
    await message.answer(f"Материалы курса:\n{course['description'] or 'Описание отсутствует.'}")


# -------------------- Admin: Управление курсами (с редактированием) --------------------
@dp.message.register(Text("Управление курсами"))
async def admin_manage_courses(message: types.Message):
    """Показываем список курсов для админа с возможностью редактирования/удаления/добавления."""
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY)
        return

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM courses ORDER BY id")
        rows = await cur.fetchall()
        courses = [dict(r) for r in rows]

    if not courses:
        await message.answer("Курсов пока нет.")
        return

    await message.answer("Список курсов (для управления):", reply_markup=kb.admin_courses_inline(courses))


@dp.callback_query.register(lambda c: c.data and c.data.startswith("admin_course:"))
async def admin_course_cb(cb: types.CallbackQuery):
    """Показ информации о курсе и кнопки управления (редактировать/удалить)."""
    await cb.answer()
    if cb.from_user.id != ADMIN_ID:
        await cb.message.answer(texts.ADMIN_ONLY)
        return

    course_id = int(cb.data.split(":", 1)[1])
    course = await db.get_course(course_id)
    if not course:
        await cb.message.answer("Курс не найден")
        return

    text = f"Курс: {course['title']}\nОписание: {course['description'] or '-'}\nЦена: {course['price'] / 100:.2f} {course['currency']}"
    inline = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Редактировать", callback_data=f"admin_course_edit:{course_id}")
        ],
        [
            types.InlineKeyboardButton(text="Удалить", callback_data=f"admin_course_delete:{course_id}")
        ],
        [
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
        ]
    ])
    await cb.message.answer(text, reply_markup=inline)


@dp.callback_query.register(lambda c: c.data and c.data.startswith("admin_course_delete:"))
async def admin_course_delete(cb: types.CallbackQuery):
    """Удаление курса (admin)."""
    await cb.answer()
    if cb.from_user.id != ADMIN_ID:
        await cb.message.answer(texts.ADMIN_ONLY)
        return

    course_id = int(cb.data.split(":", 1)[1])
    await db.delete_course(course_id)
    await cb.message.answer("Курс удалён.")


# --- Редактирование курса: инициируем выбор поля ---
@dp.callback_query.register(lambda c: c.data and c.data.startswith("admin_course_edit:"))
async def admin_course_edit_start(cb: types.CallbackQuery, state: FSMContext):
    """
    Начинаем процесс редактирования: спрашиваем, что редактировать:
    варианты: title, description (ссылки), price.
    """
    await cb.answer()
    if cb.from_user.id != ADMIN_ID:
        await cb.message.answer(texts.ADMIN_ONLY)
        return

    course_id = int(cb.data.split(":", 1)[1])
    course = await db.get_course(course_id)
    if not course:
        await cb.message.answer("Курс не найден")
        return

    # Запомним id курса в состоянии
    await state.set_state(EditCourse.waiting_for_field)
    await state.update_data(course_id=course_id)

    # Предложим варианты полей для редактирования
    inline = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Название", callback_data="edit_field:title"),
            types.InlineKeyboardButton(text="Описание / Ссылка", callback_data="edit_field:description")
        ],
        [
            types.InlineKeyboardButton(text="Цена (RUB)", callback_data="edit_field:price")
        ],
        [
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
        ]
    ])
    await cb.message.answer("Что хотите изменить?", reply_markup=inline)


@dp.callback_query.register(lambda c: c.data and c.data.startswith("edit_field:"))
async def admin_course_edit_field(cb: types.CallbackQuery, state: FSMContext):
    """Обработка выбора поля для редактирования."""
    await cb.answer()
    if cb.from_user.id != ADMIN_ID:
        await cb.message.answer(texts.ADMIN_ONLY)
        return

    # Проверим, что мы в нужном состоянии (но не обязательно — просто продолжим)
    field = cb.data.split(":", 1)[1]
    data = await state.get_data()
    if not data or "course_id" not in data:
        await cb.message.answer("Не найден курс в состоянии. Повторите действие.")
        await state.clear()
        return

    # Сохраним выбранное поле и перейдём к ожиданию нового значения
    await state.update_data(edit_field=field)
    await state.set_state(EditCourse.waiting_for_value)

    if field == "title":
        await cb.message.answer("Отправьте новое название для курса (или ❌ Отмена):")
    elif field == "description":
        await cb.message.answer("Отправьте новое описание / ссылку для курса (или ❌ Отмена):")
    elif field == "price":
        await cb.message.answer("Отправьте новую цену в рублях (пример: 499.99) (или ❌ Отмена):")
    else:
        await cb.message.answer("Неизвестное поле.")
        await state.clear()


@dp.message.register(state=EditCourse.waiting_for_value)
async def admin_course_edit_value(message: types.Message, state: FSMContext):
    """Получаем новое значение поля и применяем изменения в БД."""
    # Отмена
    if message.text.strip() == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCELLED, reply_markup=kb.main_menu())
        return

    data = await state.get_data()
    course_id: Optional[int] = data.get("course_id")
    field: Optional[str] = data.get("edit_field")

    if not course_id or not field:
        await state.clear()
        await message.answer("Ошибка состояния. Повторите действие.", reply_markup=kb.main_menu())
        return

    # Подготовим обновление в зависимости от поля
    try:
        if field == "title":
            new_title = message.text.strip()
            if not new_title:
                await message.answer("Название не может быть пустым. Попробуйте ещё раз.")
                return
            await db.update_course(course_id, title=new_title)
            await message.answer(f"Название обновлено: <b>{new_title}</b>", reply_markup=kb.main_menu())

        elif field == "description":
            new_desc = message.text.strip()
            await db.update_course(course_id, description=new_desc)
            await message.answer("Описание обновлено.", reply_markup=kb.main_menu())

        elif field == "price":
            # Парсим цену в рублях и конвертируем в копейки
            try:
                value = float(message.text.replace(",", "."))
                amount = int(round(value * 100))
                if amount <= 0:
                    raise ValueError()
            except Exception:
                await message.answer("Неверный формат цены. Введите, например: 499.99")
                return
            await db.update_course(course_id, price=amount)
            await message.answer(f"Цена обновлена: {amount / 100:.2f} {CURRENCY}", reply_markup=kb.main_menu())

        else:
            await message.answer("Неизвестное поле для редактирования.")
    except Exception as exc:
        logger.exception("Error updating course: %s", exc)
        await message.answer("Произошла ошибка при обновлении курса. Попробуйте позже.")
    finally:
        await state.clear()


# -------------------- Admin: Управление категориями --------------------
@dp.message.register(Text("Управление категориями"))
async def admin_manage_categories(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(texts.ADMIN_ONLY)
        return
    categories = await db.list_categories(active_only=False)
    await message.answer("Управление категориями:", reply_markup=kb.admin_categories_inline(categories))


@dp.callback_query.register(lambda c: c.data and c.data.startswith("admin_cat:"))
async def admin_cat_cb(cb: types.CallbackQuery):
    await cb.answer()
    if cb.from_user.id != ADMIN_ID:
        await cb.message.answer(texts.ADMIN_ONLY)
        return
    cat_id = int(cb.data.split(":", 1)[1])
    cat = await db.get_category(cat_id)
    if not cat:
        await cb.message.answer("Категория не найдена")
        return
    text = f"Категория: {cat['title']}\nАктивна: {bool(cat['is_active'])}"
    inline = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Переключить активность", callback_data=f"admin_cat_toggle:{cat_id}")],
        [types.InlineKeyboardButton(text="Удалить", callback_data=f"admin_cat_delete:{cat_id}")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
    ])
    await cb.message.answer(text, reply_markup=inline)


@dp.callback_query.register(lambda c: c.data and c.data.startswith("admin_cat_toggle:"))
async def admin_cat_toggle(cb: types.CallbackQuery):
    await cb.answer()
    if cb.from_user.id != ADMIN_ID:
        await cb.message.answer(texts.ADMIN_ONLY)
        return
    cat_id = int(cb.data.split(":", 1)[1])
    cat = await db.get_category(cat_id)
    if not cat:
        await cb.message.answer("Категория не найдена")
        return
    await db.set_category_active(cat_id, not bool(cat["is_active"]))
    await cb.message.answer("Статус категории обновлён.")


@dp.callback_query.register(lambda c: c.data and c.data.startswith("admin_cat_delete:"))
async def admin_cat_delete(cb: types.CallbackQuery):
    await cb.answer()
    if cb.from_user.id != ADMIN_ID:
        await cb.message.answer(texts.ADMIN_ONLY)
        return
    cat_id = int(cb.data.split(":", 1)[1])
    await db.delete_category(cat_id)
    await cb.message.answer("Категория удалена.")


@dp.callback_query.register(lambda c: c.data == "admin_cat_add")
async def admin_cat_add_cb(cb: types.CallbackQuery):
    await cb.answer()
    if cb.from_user.id != ADMIN_ID:
        await cb.message.answer(texts.ADMIN_ONLY)
        return
    await cb.message.answer("Введите название новой категории:")
    await AddCategory.waiting_for_title.set()


@dp.message.register(state=AddCategory.waiting_for_title)
async def add_category_title(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCELLED, reply_markup=kb.main_menu())
        return
    title = message.text.strip()
    cid = await db.add_category(title)
    await state.clear()
    await message.answer(f'Категория "{title}" добавлена с id {cid}.', reply_markup=kb.main_menu())


# -------------------- Добавление курса (admin) --------------------
@dp.callback_query.register(lambda c: c.data == "admin_course_add")
async def admin_course_add_cb(cb: types.CallbackQuery):
    await cb.answer()
    if cb.from_user.id != ADMIN_ID:
        await cb.message.answer(texts.ADMIN_ONLY)
        return
    cats = await db.list_categories(active_only=False)
    if not cats:
        await cb.message.answer("Сначала добавьте категорию через Управление категориями")
        return
    await cb.message.answer("Выберите категорию (напишите id):\n" + "\n".join([f"{c['id']}: {c['title']}" for c in cats]))
    await AddCourse.waiting_for_category.set()


@dp.message.register(state=AddCourse.waiting_for_category)
async def add_course_category(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCELLED, reply_markup=kb.main_menu())
        return
    try:
        cat_id = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный id. Введите числовой id категории.")
        return
    cat = await db.get_category(cat_id)
    if not cat:
        await message.answer("Категория не найдена.")
        return
    await state.update_data(category_id=cat_id)
    await message.answer("Введите заголовок курса:")
    await AddCourse.waiting_for_title.set()


@dp.message.register(state=AddCourse.waiting_for_title)
async def add_course_title(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCELLED, reply_markup=kb.main_menu())
        return
    await state.update_data(title=message.text)
    await message.answer("Введите описание курса:")
    await AddCourse.waiting_for_description.set()


@dp.message.register(state=AddCourse.waiting_for_description)
async def add_course_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCELLED, reply_markup=kb.main_menu())
        return
    await state.update_data(description=message.text)
    await message.answer("Введите цену в рублях (например: 499.99):")
    await AddCourse.waiting_for_price.set()


@dp.message.register(state=AddCourse.waiting_for_price)
async def add_course_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer(texts.CANCELLED, reply_markup=kb.main_menu())
        return
    try:
        value = float(message.text.replace(",", "."))
        amount = int(round(value * 100))
    except Exception:
        await message.answer("Неверный формат цены. Введите например: 499.99")
        return
    data = await state.get_data()
    category_id = data["category_id"]
    title = data["title"]
    description = data["description"]
    payload = f"payload_{secrets.token_hex(8)}"
    cid = await db.add_course(category_id, title, description, amount, CURRENCY, payload)
    await state.clear()
    await message.answer(f'Курс "{title}" добавлен с id {cid}.', reply_markup=kb.main_menu())


# -------------------- Отмена и fallback --------------------
@dp.callback_query.register(lambda c: c.data == "admin_cancel")
async def admin_cancel_cb(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    # Удаляем клавиатуру и очищаем состояние
    try:
        await cb.message.delete_reply_markup()
    except Exception:
        pass
    await state.clear()
    await cb.message.answer("Отменено.", reply_markup=kb.main_menu())


@dp.message.register(Text("❌ Отмена"))
async def cancel_by_text(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=kb.main_menu())


@dp.message.register()
async def fallback(message: types.Message):
    await message.answer("Неизвестная команда. Используйте главное меню.", reply_markup=kb.main_menu())


# -------------------- Run --------------------
async def main():
    await on_startup()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())







