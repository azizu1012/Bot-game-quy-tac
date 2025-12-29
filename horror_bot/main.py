import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from services.llm_service import load_llm

# Load biến môi trường
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Setup Bot
# Lưu ý: command_prefix="!" để dùng lệnh !sync
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    
    # 1. Load LLM
    print("\n🤖 Loading LLM model...")
    if load_llm():
        print("✓ LLM ready for game descriptions\n")
    else:
        print("⚠ LLM failed to load. Game descriptions will be limited.\n")
    
    # 2. Load Cogs
    # Chỉ load cogs, KHÔNG sync global ở đây để tránh bị chậm
    try:
        await bot.load_extension("cogs.game_commands")
        await bot.load_extension("cogs.admin_commands")
        await bot.load_extension("cogs.game_ui")
        print("✅ Cogs loaded successfully.")
    except Exception as e:
        print(f"❌ Error loading cogs: {e}")

    print("🚀 Bot is ready! Hãy gõ lệnh '!sync' trong Discord để hiện menu lệnh Slash.")

# --- Lệnh Sync Thần Thánh (Bắt buộc phải có để hiện Slash Command ngay) ---
@bot.command()
async def sync(ctx):
    """Đồng bộ lệnh Slash vào server hiện tại ngay lập tức."""
    print(f"Started syncing commands to guild {ctx.guild.id}...")
    try:
        # Sync riêng cho guild này -> Hiện ngay lập tức
        synced = await bot.tree.sync(guild=ctx.guild)
        # Hoặc copy lệnh global vào guild này
        bot.tree.copy_global_to(guild=ctx.guild)
        synced = await bot.tree.sync(guild=ctx.guild)
        
        await ctx.send(f"✅ Đã đồng bộ {len(synced)} lệnh Slash (/newgame, /join...) vào server này!")
        print("Sync complete.")
    except Exception as e:
        await ctx.send(f"❌ Lỗi sync: {e}")
        print(f"Sync error: {e}")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in .env file.")
    else:
        bot.run(DISCORD_TOKEN)