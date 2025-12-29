import aiosqlite
import os

DB_FILE = "horror_bot/database/game.db"
SCHEMA_FILE = "horror_bot/database/schema.sql"

async def get_db_connection():
    """Establishes an async connection to the SQLite database."""
    db = await aiosqlite.connect(DB_FILE)
    db.row_factory = aiosqlite.Row
    return db

async def setup_database():
    """Sets up the database by creating tables from the schema file."""
    if os.path.exists(DB_FILE):
        print("Database already exists.")
        return

    print("Setting up new database...")
    async with aiosqlite.connect(DB_FILE) as db:
        with open(SCHEMA_FILE, 'r') as f:
            schema = f.read()
        await db.executescript(schema)
        await db.commit()
    print("Database setup complete.")

async def execute_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    """A utility function to execute database queries."""
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(query, params)
        if fetchone:
            return await cursor.fetchone()
        if fetchall:
            return await cursor.fetchall()
        if commit:
            await db.commit()
            return cursor.lastrowid
