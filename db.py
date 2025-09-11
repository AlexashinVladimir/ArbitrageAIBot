import aiosqlite

DB_NAME = "database.db"

# Инициализация базы
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
                category_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                price INTEGER NOT NULL,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        """)
        await db.commit()

# --- Категории ---
async def get_categories():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, name FROM categories")
        rows = await cursor.fetchall()
        return [{"id": row[0], "name": row[1]} for row in rows]

async def add_category(name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await db.commit()

async def delete_category(category_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()

# --- Курсы ---
async def get_courses_by_category(category_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id, title, description, price FROM courses WHERE category_id = ?",
            (category_id,),
        )
        rows = await cursor.fetchall()
        return [
            {"id": row[0], "title": row[1], "description": row[2], "price": row[3]}
            for row in rows
        ]

async def get_course(course_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id, category_id, title, description, price FROM courses WHERE id = ?",
            (course_id,),
        )
        row = await cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "category_id": row[1],
                "title": row[2],
                "description": row[3],
                "price": row[4],
            }
        return None

async def add_course(category_id: int, title: str, description: str, price: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO courses (category_id, title, description, price) VALUES (?, ?, ?, ?)",
            (category_id, title, description, price),
        )
        await db.commit()

async def delete_course(course_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        await db.commit()


