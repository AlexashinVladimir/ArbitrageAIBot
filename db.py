import aiosqlite
import os
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "database.sqlite")


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
            title TEXT NOT NULL,
            description TEXT,
            price INTEGER,
            link TEXT,
            category_id INTEGER,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
        """)
        await db.commit()


# --- Categories ---
async def get_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, title FROM categories")
        rows = await cursor.fetchall()
        return [{"id": row[0], "title": row[1]} for row in rows]


async def add_category(title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO categories (title) VALUES (?)", (title,))
        await db.commit()


# --- Courses ---
async def get_courses(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, title FROM courses WHERE category_id = ?", (category_id,)
        )
        rows = await cursor.fetchall()
        return [{"id": row[0], "title": row[1]} for row in rows]


async def get_course(course_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, title, description, price, link FROM courses WHERE id = ?", (course_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "price": row[3],
                "link": row[4],
            }
        return None


async def add_course(title: str, description: str, price: int, link: str, category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO courses (title, description, price, link, category_id) VALUES (?, ?, ?, ?, ?)",
            (title, description, price, link, category_id),
        )
        await db.commit()

