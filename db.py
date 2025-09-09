"""
db.py — слой доступа к SQLite (aiosqlite).
Содержит init_db(path) и CRUD функции.
"""

import aiosqlite
import os
from typing import Optional, List, Dict, Any

DB_PATH = os.getenv("DB_PATH", "data.db")

async def init_db(path: Optional[str] = None):
    global DB_PATH
    if path:
        DB_PATH = path
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            is_admin INTEGER DEFAULT 0
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL UNIQUE
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            link TEXT,
            payload TEXT UNIQUE,
            FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            UNIQUE(user_id, course_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        );
        """)
        await db.commit()

# Users
async def ensure_user(tg_id: int, is_admin: bool = False) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,))
        r = await cur.fetchone()
        if r:
            return r["id"]
        cur = await db.execute("INSERT INTO users (tg_id, is_admin) VALUES (?, ?)", (tg_id, int(is_admin)))
        await db.commit()
        return cur.lastrowid

# Categories
async def add_category(title: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO categories (title) VALUES (?)", (title,))
        await db.commit()
        return cur.lastrowid

async def list_categories(active_only: bool = True) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM categories ORDER BY id")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def get_category(cat_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM categories WHERE id=?", (cat_id,))
        r = await cur.fetchone()
        return dict(r) if r else None

async def delete_category(cat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        await db.commit()

# Courses
async def add_course(category_id: int, title: str, description: str, price: int, link: str, payload: Optional[str] = None) -> int:
    if payload is None:
        import secrets
        payload = f"course_{secrets.token_hex(8)}"
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO courses (category_id, title, description, price, link, payload) VALUES (?, ?, ?, ?, ?, ?)",
            (category_id, title, description, price, link, payload)
        )
        await db.commit()
        return cur.lastrowid

async def list_courses_by_category(cat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses WHERE category_id=? ORDER BY id", (cat_id,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def list_courses():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses ORDER BY id")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def get_course(course_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses WHERE id=?", (course_id,))
        r = await cur.fetchone()
        return dict(r) if r else None

async def get_course_by_payload(payload: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM courses WHERE payload=?", (payload,))
        r = await cur.fetchone()
        return dict(r) if r else None

async def update_course_field(course_id: int, field: str, value):
    allowed = {"title", "description", "price", "link", "category_id"}
    if field not in allowed:
        raise ValueError("Field not allowed")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE courses SET {field}=? WHERE id=?", (value, course_id))
        await db.commit()

async def delete_course(course_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM courses WHERE id=?", (course_id,))
        await db.commit()

# Purchases
async def record_purchase(user_id: int, course_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO purchases (user_id, course_id) VALUES (?, ?)", (user_id, course_id))
        await db.commit()


