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
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    
    # 1. Setup Database
    print("\n🗄️ Setting up database...")
    try:
        await setup_database()
        print("✅ Database ready.")
    except Exception as e:
        print(f"❌ Database error: {e}")
    
    # 2. Load LLM
    print("\n🤖 Loading LLM model...")
    if load_llm():
        print("✓ LLM ready for game descriptions\n")
    else:
        print("⚠ LLM failed to load. Game descriptions will be limited.\n")
    
    # 3. Load Cogs
    try:
        await bot.load_extension("cogs.game_commands")
        await bot.load_extension("cogs.admin_commands")
        await bot.load_extension("cogs.game_ui")
        print("✅ Cogs loaded successfully.")
    except Exception as e:
        print(f"❌ Error loading cogs: {e}")

    # 4. AUTO-SYNC SLASH COMMANDS (no need for !sync)
    print("\n🔄 Auto-syncing slash commands...")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Successfully synced {len(synced)} slash commands globally!")
        print("🚀 Bot is ready! Use /newgame, /join, /endgame commands now.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in .env file.")
    else:
        bot.run(DISCORD_TOKEN)