from aiogram.fsm.state import StatesGroup, State


class AddCategory(StatesGroup):
    waiting_for_title = State()


class AddCourse(StatesGroup):
    waiting_for_category = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_link = State()
