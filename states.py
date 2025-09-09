from aiogram.fsm.state import StatesGroup, State

class AdminStates(StatesGroup):
    add_category = State()
    add_course_category = State()
    add_course_title = State()
    add_course_description = State()
    add_course_price = State()
    add_course_link = State()
