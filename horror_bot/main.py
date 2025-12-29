import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from services.llm_service import load_llm
from database.db_manager import setup_database

# Load biến môi trường
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Setup Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Đã đăng nhập dưới tên: {bot.user} (ID: {bot.user.id})')
    print('=' * 50)
    
    # 1. Setup Database
    print("\n📦 Khởi tạo cơ sở dữ liệu...")
    try:
        await setup_database()
        print("✅ Cơ sở dữ liệu sẵn sàng.")
    except Exception as e:
        print(f"❌ Lỗi cơ sở dữ liệu: {e}")
    
    # 2. Load LLM
    print("\n🤖 Tải mô hình AI...")
    if load_llm():
        print("✅ LLM sẵn sàng cho mô tả game\n")
    else:
        print("⚠️  LLM không thể tải. Mô tả sẽ bị hạn chế.\n")
    
    # 3. Load Cogs
    try:
        await bot.load_extension("cogs.game_commands")
        await bot.load_extension("cogs.admin_commands")
        await bot.load_extension("cogs.game_ui")
        print("✅ Các plugin đã tải thành công.")
    except Exception as e:
        print(f"❌ Lỗi tải plugin: {e}")

    # 4. AUTO-SYNC SLASH COMMANDS
    print("\n🔄 Đồng bộ hóa slash commands...")
    try:
        # Xóa toàn bộ slash commands cũ để force refresh
        await bot.tree.clear_commands(sync_to_guild=None)
        await bot.tree.sync()
        
        # Đồng bộ hóa lại slash commands mới
        synced = await bot.tree.sync()
        print(f"✅ Đã đồng bộ {len(synced)} slash commands!")
        for cmd in synced:
            print(f"   - /{cmd.name}")
        print("\n" + "=" * 50)
        print("🚀 Bot sẵn sàng! Sử dụng /newgame, /join, /endgame")
        print("=" * 50)
    except Exception as e:
        print(f"❌ Lỗi đồng bộ hóa: {e}")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in .env file.")
    else:
        bot.run(DISCORD_TOKEN)