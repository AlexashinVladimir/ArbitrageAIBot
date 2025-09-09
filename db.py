import aiosqlite
from typing import List, Optional, Tuple

DB_PATH = "courses.db"

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    price INTEGER NOT NULL, -- в целых рублях
    link TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT,
    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    telegram_payment_charge_id TEXT,
    provider_payment_charge_id TEXT,
    created_at TEXT,
    UNIQUE(user_id, course_id)
);
"""

async def init_db(path: str = DB_PATH):
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        await db.commit()

# --- Categories ---
async def add_category(name: str, path: str = DB_PATH) -> int:
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO categories(name, is_active, created_at) VALUES (?, ?, datetime('now'))",
            (name, 1)
        )
        await db.commit()
        return cur.lastrowid

async def list_categories(active_only: bool = True, path: str = DB_PATH) -> List[Tuple]:
    async with aiosqlite.connect(path) as db:
        if active_only:
            cursor = await db.execute("SELECT id, name, is_active FROM categories WHERE is_active=1 ORDER BY id")
        else:
            cursor = await db.execute("SELECT id, name, is_active FROM categories ORDER BY id")
        return await cursor.fetchall()

async def get_category(cat_id: int, path: str = DB_PATH) -> Optional[Tuple]:
    async with aiosqlite.connect(path) as db:
        cur = await db.execute("SELECT id, name, is_active FROM categories WHERE id=?", (cat_id,))
        return await cur.fetchone()

async def toggle_category(cat_id: int, path: str = DB_PATH):
    async with aiosqlite.connect(path) as db:
        cur = await db.execute("SELECT is_active FROM categories WHERE id=?", (cat_id,))
        row = await cur.fetchone()
        if not row:
            return False
        new = 0 if row[0] else 1
        await db.execute("UPDATE categories SET is_active=? WHERE id=?", (new, cat_id))
        await db.commit()
        return True

async def delete_category(cat_id: int, path: str = DB_PATH):
    async with aiosqlite.connect(path) as db:
        await db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        await db.commit()

# --- Courses ---
async def add_course(category_id: int, title: str, description: str, price: int, link: str, path: str = DB_PATH) -> int:
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            "INSERT INTO courses(category_id, title, description, price, link, is_active, created_at) VALUES (?, ?, ?, ?, ?, 1, datetime('now'))",
            (category_id, title, description, price, link)
        )
        await db.commit()
        return cur.lastrowid

async def list_courses_by_category(category_id: int, active_only: bool = True, path: str = DB_PATH):
    async with aiosqlite.connect(path) as db:
        if active_only:
            cur = await db.execute(
                "SELECT id, title, description, price, link, is_active FROM courses WHERE category_id=? AND is_active=1 ORDER BY id",
                (category_id,)
            )
        else:
            cur = await db.execute(
                "SELECT id, title, description, price, link, is_active FROM courses WHERE category_id=? ORDER BY id",
                (category_id,)
            )
        return await cur.fetchall()

async def get_course(course_id: int, path: str = DB_PATH):
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            "SELECT id, category_id, title, description, price, link, is_active FROM courses WHERE id=?",
            (course_id,)
        )
        return await cur.fetchone()

async def toggle_course(course_id: int, path: str = DB_PATH):
    async with aiosqlite.connect(path) as db:
        cur = await db.execute("SELECT is_active FROM courses WHERE id=?", (course_id,))
        row = await cur.fetchone()
        if not row:
            return False
        new = 0 if row[0] else 1
        await db.execute("UPDATE courses SET is_active=? WHERE id=?", (new, course_id))
        await db.commit()
        return True

async def delete_course(course_id: int, path: str = DB_PATH):
    async with aiosqlite.connect(path) as db:
        await db.execute("DELETE FROM courses WHERE id=?", (course_id,))
        await db.commit()

# --- Purchases ---
async def add_purchase(user_id: int, course_id: int, amount: int, currency: str,
                       telegram_charge_id: str = None, provider_charge_id: str = None, path: str = DB_PATH):
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO purchases(user_id, course_id, amount, currency, telegram_payment_charge_id, provider_payment_charge_id, created_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (user_id, course_id, amount, currency, telegram_charge_id, provider_charge_id)
        )
        await db.commit()
