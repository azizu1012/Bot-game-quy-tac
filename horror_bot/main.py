# -*- coding: utf-8 -*-
import discord
import os
import asyncio
from discord.ext import commands, tasks
from dotenv import load_dotenv
from services.llm_service import load_llm
from database.db_manager import setup_database
from services.recovery_service import restore_from_backup, create_backup, cleanup_old_backups

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@tasks.loop(minutes=10)
async def auto_backup():
    """Auto-backup mỗi 10 phút."""
    try:
        await create_backup()
        await cleanup_old_backups(keep_count=5)
    except Exception as e:
        print(f"⚠️ Error in auto_backup: {e}")

@bot.event
async def on_ready():
    """Event that runs when the bot is connected and ready."""
    print(f'✅ Đã đăng nhập dưới tên: {bot.user} (ID: {bot.user.id})')
    print('=' * 50)
    
    # 0. Restore from backup if needed
    print("\n🔄 Kiểm tra backup...")
    await restore_from_backup()
    
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
    
    # 3. Auto-sync slash commands
    print("🔄 Đồng bộ hóa slash commands...")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Đã sync {len(synced)} slash commands:")
        for cmd in synced:
            print(f"   - /{cmd.name}")
    except Exception as e:
        print(f"⚠️ Lỗi sync commands: {e}")
    
    # Start backup task
    if not auto_backup.is_running():
        auto_backup.start()
        print("\n🔄 Bắt đầu auto-backup (mỗi 10 phút)")
    
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
            cogs = ["cogs.game_commands", "cogs.admin_commands", "cogs.game_ui"]
            for cog in cogs:
                try:
                    await bot.load_extension(cog)
                except Exception as e:
                    # Ignore if already loaded
                    if "already loaded" not in str(e):
                        print(f"❌ Lỗi tải {cog}: {e}")
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
