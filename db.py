"""
db.py — работа с SQLite: категории, курсы, покупки.
"""

import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "database.db")


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
            category_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            link TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            UNIQUE(user_id, course_id),
            FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
        )
        """)

        await db.commit()



