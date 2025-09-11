# states.py
from aiogram.fsm.state import StatesGroup, State


# Добавление категории
class AddCategory(StatesGroup):
    waiting_for_title = State()


# Добавление курса
class AddCourse(StatesGroup):
    waiting_for_category = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_link = State()


# Редактирование курса
class EditCourse(StatesGroup):
    waiting_for_new_title = State()
    waiting_for_new_description = State()
    waiting_for_new_price = State()
    waiting_for_new_link = State()
