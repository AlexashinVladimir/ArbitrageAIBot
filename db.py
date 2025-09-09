"""Работа с базой данных (SQLite) — асинхронно через aiosqlite."""


# Courses operations
async def add_course(category_id: int, title: str, description: str, price: int, currency: str, payload: str) -> int:
async with aiosqlite.connect(DB_PATH) as db:
cur = await db.execute(
"INSERT INTO courses (category_id, title, description, price, currency, payload) VALUES (?,?,?,?,?,?)",
(category_id, title, description, price, currency, payload),
)
await db.commit()
return cur.lastrowid


async def update_course(course_id: int, **fields):
if not fields:
return
keys = ",".join([f"{k}=?" for k in fields.keys()])
values = list(fields.values())
values.append(course_id)
async with aiosqlite.connect(DB_PATH) as db:
await db.execute(f"UPDATE courses SET {keys} WHERE id=?", values)
await db.commit()


async def delete_course(course_id: int):
async with aiosqlite.connect(DB_PATH) as db:
await db.execute("DELETE FROM courses WHERE id=?", (course_id,))
await db.commit()


async def list_courses_by_category(category_id: int) -> List[Dict[str, Any]]:
async with aiosqlite.connect(DB_PATH) as db:
db.row_factory = aiosqlite.Row
cur = await db.execute("SELECT * FROM courses WHERE category_id=? ORDER BY id", (category_id,))
rows = await cur.fetchall()
return [dict(r) for r in rows]


async def get_course_by_payload(payload: str) -> Optional[Dict[str, Any]]:
async with aiosqlite.connect(DB_PATH) as db:
db.row_factory = aiosqlite.Row
cur = await db.execute("SELECT * FROM courses WHERE payload=?", (payload,))
r = await cur.fetchone()
return dict(r) if r else None


async def get_course(course_id: int) -> Optional[Dict[str, Any]]:
async with aiosqlite.connect(DB_PATH) as db:
db.row_factory = aiosqlite.Row
cur = await db.execute("SELECT * FROM courses WHERE id=?", (course_id,))
r = await cur.fetchone()
return dict(r) if r else None


# Users and purchases
async def ensure_user(tg_id: int, is_admin: bool = False) -> int:
async with aiosqlite.connect(DB_PATH) as db:
db.row_factory = aiosqlite.Row
cur = await db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
r = await cur.fetchone()
if r:
return r['id']
cur = await db.execute("INSERT INTO users (tg_id, is_admin) VALUES (?,?)", (tg_id, 1 if is_admin else 0))
await db.commit()
return cur.lastrowid


async def record_purchase(user_id: int, course_id: int, pay_date: str, telegram_payment_payload: str):
async with aiosqlite.connect(DB_PATH) as db:
await db.execute(
"INSERT INTO purchases (user_id, course_id, pay_date, telegram_payment_payload) VALUES (?,?,?,?)",
(user_id, course_id, pay_date, telegram_payment_payload),
)
await db.commit()


async def user_has_course(user_tg_id: int, course_id: int) -> bool:
async with aiosqlite.connect(DB_PATH) as db:
db.row_factory = aiosqlite.Row
cur = await db.execute("SELECT u.id FROM users u JOIN purchases p ON u.id = p.user_id WHERE u.tg_id=? AND p.course_id=?", (user_tg_id, course_id))
r = await cur.fetchone()
return bool(r)



