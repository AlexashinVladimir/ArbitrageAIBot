import aiosqlite
import asyncio

DB_PATH = "db.sqlite"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                active INTEGER DEFAULT 1
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
                active INTEGER DEFAULT 1,
                FOREIGN KEY(category_id) REFERENCES categories(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS purchases(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                course_id INTEGER,
                amount REAL,
                currency TEXT,
                telegram_charge_id TEXT,
                provider_charge_id TEXT
            )
        """)
        await db.commit()

# --- Категории ---
async def list_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM categories")
        rows = await cursor.fetchall()
        return rows

async def add_category(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO categories(name) VALUES(?)", (name,))
        await db.commit()

async def toggle_category(cat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE categories SET active = 1 - active WHERE id = ?", (cat_id,))
        await db.commit()

# --- Курсы ---
async def list_courses_by_category(category_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM courses WHERE category_id = ?", (category_id,))
        return await cursor.fetchall()

async def get_course(course_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        return await cursor.fetchone()

async def add_course(category_id, title, description, price, link):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO courses(category_id, title, description, price, link) VALUES(?,?,?,?,?)",
            (category_id, title, description, price, link)
        )
        await db.commit()

async def toggle_course(course_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE courses SET active = 1 - active WHERE id = ?", (course_id,))
        await db.commit()

# --- Покупки ---
async def add_purchase(user_id, course_id, amount, currency, telegram_charge_id, provider_charge_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO purchases(user_id, course_id, amount, currency, telegram_charge_id, provider_charge_id) VALUES(?,?,?,?,?,?)",
            (user_id, course_id, amount, currency, telegram_charge_id, provider_charge_id)
        )
        await db.commit()


