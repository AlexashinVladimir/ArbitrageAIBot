import aiosqlite
import asyncio

DB_NAME = "arbitrage.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            link TEXT NOT NULL,
            category_id INTEGER,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
        """)
        await db.commit()


# === Категории ===
async def add_category(name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await db.commit()


async def get_categories():
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT id, name FROM categories")
        rows = await cur.fetchall()
        return [{"id": row[0], "name": row[1]} for row in rows]


async def delete_category(category_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.execute("DELETE FROM courses WHERE category_id = ?", (category_id,))
        await db.commit()


# === Курсы ===
async def add_course(title: str, description: str, price: int, link: str, category_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        INSERT INTO courses (title, description, price, link, category_id)
        VALUES (?, ?, ?, ?, ?)
        """, (title, description, price, link, category_id))
        await db.commit()


async def get_courses(category_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("""
        SELECT id, title, description, price, link
        FROM courses
        WHERE category_id = ?
        """, (category_id,))
        rows = await cur.fetchall()
        return [
            {"id": row[0], "title": row[1], "description": row[2], "price": row[3], "link": row[4]}
            for row in rows
        ]


async def delete_course(course_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        await db.commit()


async def update_course(course_id: int, title: str, description: str, price: int, link: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        UPDATE courses
        SET title = ?, description = ?, price = ?, link = ?
        WHERE id = ?
        """, (title, description, price, link, course_id))
        await db.commit()


# Если запускаем напрямую → создаём базу
if __name__ == "__main__":
    asyncio.run(init_db())
    print("✅ База данных и таблицы успешно созданы")



