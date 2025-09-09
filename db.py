"""
db.py — работа с SQLite (курсы, категории, пользователи).
"""

import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "data.db")


async def init_db(path: str = DB_PATH):
    global DB_PATH
    DB_PATH = path
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            is_admin INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            active INTEGER DEFAULT 1
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title TEXT,
            description TEXT,
            price INTEGER,
            currency TEXT,
            link TEXT,
            payload TEXT UNIQUE,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            course_id INTEGER,
            date TEXT,
            payload TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
        """)
        await db.commit()


async def ensure_user(tg_id: int, is_admin: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,))
        row = await cur.fetchone()
        if row:
            return row[0]
        await db.execute("INSERT INTO users (tg_id, is_admin) VALUES (?, ?)", (tg_id, int(is_admin)))
        await db.commit()
        return (await db.execute("SELECT last_insert_rowid()")).fetchone()


async def add_category(title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO categories (title, active) VALUES (?, 1)", (title,))
        await db.commit()


async def list_categories(active_only=True):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if active_only:
            cur = await db.execute("SELECT * FROM categories WHERE active=1 ORDER BY id")
        else:
            cur = await db.execute("SELECT * FROM categories ORDER BY id")
        return [dict(r) for r in await cur.fetchall()]


async def add_course(category_id, title, description, price, currency, link, payload):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO courses (category_id, title, description, price, currency, link, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (category_id, title, description, price, currency, link, payload)
        )
        await db.commit()


async def list_courses_by_category(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses WHERE category_id=?", (category_id,))
        return [dict(r) for r in await cur.fetchall()]


async def get_course(course_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses WHERE id=?", (course_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_course_by_payload(payload: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses WHERE payload=?", (payload,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def record_purchase(user_id, course_id, date, payload):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO purchases (user_id, course_id, date, payload) VALUES (?, ?, ?, ?)",
            (user_id, course_id, date, payload)
        )
        await db.commit()





