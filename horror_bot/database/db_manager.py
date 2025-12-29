import aiosqlite
import os

# --- CẤU HÌNH ĐƯỜNG DẪN TUYỆT ĐỐI (QUAN TRỌNG) ---
# Lấy đường dẫn thư mục chứa file db_manager.py (tức là thư mục database/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# File DB sẽ nằm ở thư mục cha (horror_bot/)
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "horror_bot.db")

# File Schema nằm ngay trong thư mục database/
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

async def get_db_connection():
    """Get a database connection with row factory set to aiosqlite.Row."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

async def setup_database():
    """Hàm này sẽ đọc file schema.sql và tạo bảng"""
    print(f"🛠️ Đang kiểm tra Database tại: {DB_PATH}")
    print(f"📄 Đang đọc Schema tại: {SCHEMA_PATH}")

    if not os.path.exists(SCHEMA_PATH):
        print(f"❌ LỖI NGHIÊM TRỌNG: Không tìm thấy file schema.sql tại {SCHEMA_PATH}")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema = f.read()
            
            # Kiểm tra file có rỗng không
            if not schema.strip():
                print("❌ LỖI: File schema.sql bị rỗng! Hãy copy nội dung SQL vào.")
                return

            try:
                await db.executescript(schema)
                await db.commit()
                print("✅ Đã chạy lệnh tạo bảng thành công.")
            except Exception as e:
                print(f"❌ Lỗi SQL khi tạo bảng: {e}")

async def execute_query(query, params=(), commit=False, fetchone=False, fetchall=False):
    """Hàm tiện ích để chạy query SQL an toàn (trả về dict, không phải Row)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            result = None
            if fetchone:
                row = await cursor.fetchone()
                result = dict(row) if row else None
            elif fetchall:
                rows = await cursor.fetchall()
                result = [dict(row) for row in rows] if rows else []
            
            if commit:
                await db.commit()
            return result