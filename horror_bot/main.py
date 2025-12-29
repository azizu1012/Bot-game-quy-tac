import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from services.llm_service import load_llm
from database.db_manager import setup_database

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Event that runs when the bot is connected and ready."""
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
    
    print("\n" + "=" * 50)
    print("🚀 Bot sẵn sàng! Sử dụng /newgame, /join, /endgame")
    print("==================================================")

async def main():
    """Main function to load cogs and run the bot."""
    if not DISCORD_TOKEN:
        print("❌ Error: DISCORD_TOKEN not found in .env file.")
        return

    # Load Cogs before starting the bot
    print("🔌 Đang tải các plugin (cogs)...")
    async with bot:
        try:
            await bot.load_extension("cogs.game_commands")
            await bot.load_extension("cogs.admin_commands")
            await bot.load_extension("cogs.game_ui")
            print("✅ Các plugin đã tải thành công.")
        except Exception as e:
            print(f"❌ Lỗi tải plugin: {e}")
            return  # Exit if cogs fail to load

        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nℹ️ Bot đã tắt.")
    except Exception as e:
        print(f"❌ Lỗi không xác định khi chạy bot: {e}")
