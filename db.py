"""
db.py — работа с базой SQLite (aiosqlite).
Хранение пользователей, категорий, курсов и покупок.
"""

import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "data.db")


# -------------------- Init --------------------
async def init_db(path: str = DB_PATH):
    async with aiosqlite.connect(path) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE,
                is_admin BOOLEAN DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                active BOOLEAN DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                currency TEXT DEFAULT 'RUB',
                payload TEXT UNIQUE,
                FOREIGN KEY(category_id) REFERENCES categories(id)
            );
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                course_id INTEGER,
                pay_time TEXT,
                payload TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(course_id) REFERENCES courses(id)
            );
            """
        )
        await db.commit()


# -------------------- Users --------------------
async def ensure_user(tg_id: int, is_admin: bool = False) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        if row:
            return row["id"]
        cur = await db.execute(
            "INSERT INTO users (tg_id, is_admin) VALUES (?, ?)",
            (tg_id, int(is_admin)),
        )
        await db.commit()
        return cur.lastrowid


# -------------------- Categories --------------------
async def list_categories(active_only: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if active_only:
            cur = await db.execute("SELECT * FROM categories WHERE active=1 ORDER BY id")
        else:
            cur = await db.execute("SELECT * FROM categories ORDER BY id")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def add_category(title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO categories (title) VALUES (?)", (title,))
        await db.commit()


async def delete_category(cat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        await db.commit()


# -------------------- Courses --------------------
async def list_courses_by_category(cat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM courses WHERE category_id = ? ORDER BY id", (cat_id,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_course(course_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_course_by_payload(payload: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses WHERE payload = ?", (payload,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_course(category_id: int, title: str, description: str, price: int, currency: str):
    payload = f"course_{os.urandom(6).hex()}"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO courses (category_id, title, description, price, currency, payload) VALUES (?, ?, ?, ?, ?, ?)",
            (category_id, title, description, price, currency, payload),
        )
        await db.commit()


async def update_course_field(course_id: int, field: str, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE courses SET {field} = ? WHERE id = ?", (value, course_id))
        await db.commit()


async def delete_course(course_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        await db.commit()


# -------------------- Purchases --------------------
async def record_purchase(user_id: int, course_id: int, pay_time: str, payload: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO purchases (user_id, course_id, pay_time, payload) VALUES (?, ?, ?, ?)",
            (user_id, course_id, pay_time, payload),
        )
        await db.commit()




