import aiosqlite

DB_NAME = "database.db"


async def create_tables():
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица категорий
        await db.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
        """)

        # Таблица курсов (с описанием)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title TEXT,
            description TEXT,
            price INTEGER,
            link TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
        """)

        await db.commit()


# Категории
async def add_category(name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await db.commit()


async def get_categories():
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT id, name FROM categories")
        rows = await cur.fetchall()
        return [{"id": row[0], "name": row[1]} for row in rows]


async def delete_category(category_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM categories WHERE id=?", (category_id,))
        await db.execute("DELETE FROM courses WHERE category_id=?", (category_id,))
        await db.commit()


# Курсы
async def add_course(category_id: int, title: str, description: str, price: int, link: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO courses (category_id, title, description, price, link) VALUES (?, ?, ?, ?, ?)",
            (category_id, title, description, price, link)
        )
        await db.commit()


async def get_courses(category_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT id, title, description, price, link FROM courses WHERE category_id=?",
            (category_id,)
        )
        rows = await cur.fetchall()
        return [
            {"id": row[0], "title": row[1], "description": row[2], "price": row[3], "link": row[4]}
            for row in rows
        ]


async def delete_course(course_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM courses WHERE id=?", (course_id,))
        await db.commit()

