class AddCategory(StatesGroup):
    waiting_name = State()

class ManageCategory(StatesGroup):
    waiting_category = State()

class AddCourse(StatesGroup):
    waiting_category = State()
    waiting_title = State()
    waiting_description = State()
    waiting_price = State()
    waiting_link = State()

class ManageCourse(StatesGroup):
    waiting_course = State()

