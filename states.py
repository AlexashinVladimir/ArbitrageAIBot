from aiogram.fsm.state import State, StatesGroup

class AddCategory(StatesGroup):
    waiting_name = State()

class AddCourse(StatesGroup):
    waiting_category = State()
    waiting_name = State()
    waiting_description = State()
    waiting_price = State()
