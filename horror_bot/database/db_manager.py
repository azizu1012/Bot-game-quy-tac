import aiosqlite
import os

DB_PATH = "horror_bot.db"
SCHEMA_PATH = "database/schema.sql"

async def get_db_connection():
    return await aiosqlite.connect(DB_PATH)

async def setup_database():
    """Hàm này sẽ đọc file schema.sql và tạo bảng nếu chưa có"""
    if not os.path.exists(SCHEMA_PATH):
        print(f"❌ Error: Schema file not found at {SCHEMA_PATH}")
        return

    print("Checking database schema...")
    async with aiosqlite.connect(DB_PATH) as db:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema = f.read()
            await db.executescript(schema)
            await db.commit()
    print("✅ Database schema initialized.")

async def execute_query(query, params=(), commit=False, fetchone=False, fetchall=False):
    """Hàm tiện ích để chạy query SQL an toàn"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row # Để kết quả trả về dạng Dictionary
        async with db.execute(query, params) as cursor:
            result = None
            if fetchone:
                result = await cursor.fetchone()
            elif fetchall:
                result = await cursor.fetchall()
            
            if commit:
                await db.commit()
            return result