# states.py
from aiogram.fsm.state import StatesGroup, State

class AddCategory(StatesGroup):
    waiting_for_title = State()

class AddCourse(StatesGroup):
    choosing_category = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_link = State()

class EditCategory(StatesGroup):
    waiting_for_new_title = State()

class EditCourse(StatesGroup):
    waiting_for_field_choice = State()
    waiting_for_new_value = State()
