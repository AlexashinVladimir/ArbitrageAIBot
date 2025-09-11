# db.py
import aiosqlite
import os
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "database.db")


async def create_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL UNIQUE
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            price INTEGER DEFAULT 0,
            link TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );
        """)
        await db.commit()


# ---------- Categories ----------
async def add_category(title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO categories (title) VALUES (?)", (title,))
        await db.commit()


async def get_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, title FROM categories ORDER BY id")
        rows = await cur.fetchall()
        return [{"id": r[0], "title": r[1]} for r in rows]


async def update_category(category_id: int, new_title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE categories SET title = ? WHERE id = ?", (new_title, category_id))
        await db.commit()


async def delete_category(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.execute("UPDATE courses SET category_id = NULL WHERE category_id = ?", (category_id,))
        await db.commit()


# ---------- Courses ----------
# signature: add_course(category_id, title, description, price, link)
async def add_course(category_id: int, title: str, description: str, price: int, link: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO courses (category_id, title, description, price, link) VALUES (?, ?, ?, ?, ?)",
            (category_id, title, description, price, link)
        )
        await db.commit()


async def get_courses_by_category(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, title, description, price, link FROM courses WHERE category_id = ? ORDER BY id",
            (category_id,)
        )
        rows = await cur.fetchall()
        return [
            {"id": r[0], "title": r[1], "description": r[2], "price": r[3], "link": r[4]}
            for r in rows
        ]


async def get_course(course_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, category_id, title, description, price, link FROM courses WHERE id = ?",
            (course_id,)
        )
        r = await cur.fetchone()
        if not r:
            return None
        return {"id": r[0], "category_id": r[1], "title": r[2], "description": r[3], "price": r[4], "link": r[5]}


async def get_all_courses():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, category_id, title, description, price, link FROM courses ORDER BY id")
        rows = await cur.fetchall()
        return [
            {"id": r[0], "category_id": r[1], "title": r[2], "description": r[3], "price": r[4], "link": r[5]}
            for r in rows
        ]


async def update_course(course_id: int, title: str, description: str, price: int, link: str, category_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if category_id is None:
            await db.execute(
                "UPDATE courses SET title = ?, description = ?, price = ?, link = ? WHERE id = ?",
                (title, description, price, link, course_id)
            )
        else:
            await db.execute(
                "UPDATE courses SET title = ?, description = ?, price = ?, link = ?, category_id = ? WHERE id = ?",
                (title, description, price, link, category_id, course_id)
            )
        await db.commit()


async def update_course_field(course_id: int, field: str, value):
    if field not in ("title", "description", "price", "link", "category_id"):
        raise ValueError("Unsupported field")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE courses SET {field} = ? WHERE id = ?", (value, course_id))
        await db.commit()


async def delete_course(course_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        await db.commit()


# If run directly — create tables
if __name__ == "__main__":
    import asyncio
    asyncio.run(create_tables())
    print("DB ready.")

