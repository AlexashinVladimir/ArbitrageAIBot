import aiosqlite

DB_NAME = "courses.db"

async def init_db():
    """Создаёт таблицу, если её нет"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            price INTEGER NOT NULL,
            link TEXT NOT NULL
        )
        """)
        await db.commit()

async def add_course(title: str, description: str, price: int, link: str):
    """Добавление нового курса"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO courses (title, description, price, link) VALUES (?, ?, ?, ?)",
            (title, description, price, link)
        )
        await db.commit()

async def get_courses():
    """Возвращает список всех курсов"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM courses")
        return await cursor.fetchall()

async def get_course(course_id: int):
    """Возвращает курс по ID"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        return await cursor.fetchone()

async def delete_course(course_id: int):
    """Удаляет курс по ID"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        await db.commit()
