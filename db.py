import aiosqlite

DB_PATH = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS courses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            price REAL,
            link TEXT,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
        """)
        await db.commit()

async def get_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name FROM categories")
        return await cursor.fetchall()

async def add_category(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO categories(name) VALUES(?)", (name,))
        await db.commit()

async def get_courses(category_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, category_id, title, description, price, link FROM courses WHERE category_id=?",
            (category_id,)
        )
        return await cursor.fetchall()

async def add_course(category_id, title, description, price, link):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO courses(category_id, title, description, price, link) VALUES(?,?,?,?,?)",
            (category_id, title, description, price, link)
        )
        await db.commit()

async def delete_category(category_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM categories WHERE id=?", (category_id,))
        await db.execute("DELETE FROM courses WHERE category_id=?", (category_id,))
        await db.commit()

async def delete_course(course_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM courses WHERE id=?", (course_id,))
        await db.commit()


