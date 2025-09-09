from aiogram.fsm.state import StatesGroup, State

class AddCategory(StatesGroup):
    waiting_name = State()

class AddCourse(StatesGroup):
    waiting_category = State()
    waiting_title = State()
    waiting_description = State()
    waiting_price = State()
    waiting_link = State()
