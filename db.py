import aiosqlite

DB_PATH = "data.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            price INTEGER,
            link TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
        """)
        await db.commit()


# ------------------ CATEGORIES ------------------
async def add_category(title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO categories (title) VALUES (?)", (title,))
        await db.commit()


async def get_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM categories")
        return await cur.fetchall()


async def delete_category(cat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        await db.commit()


# ------------------ COURSES ------------------
async def add_course(category_id: int, title: str, description: str, price: int, link: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO courses (category_id, title, description, price, link) VALUES (?, ?, ?, ?, ?)",
            (category_id, title, description, price, link)
        )
        await db.commit()


async def get_courses():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses")
        return await cur.fetchall()


async def get_courses_by_category(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses WHERE category_id=?", (category_id,))
        return await cur.fetchall()


async def get_course(course_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses WHERE id=?", (course_id,))
        return await cur.fetchone()


async def delete_course(course_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM courses WHERE id=?", (course_id,))
        await db.commit()


