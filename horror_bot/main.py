import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from services.llm_service import load_llm

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    
    # Load LLM model
    print("\n🤖 Loading LLM model...")
    if load_llm():
        print("✓ LLM ready for game descriptions\n")
    else:
        print("⚠ LLM failed to load. Game descriptions will be limited.\n")
    
    # Load cogs
    await bot.load_extension("cogs.game_commands")
    await bot.load_extension("cogs.admin_commands")
    await bot.load_extension("cogs.game_ui")
    print("Cogs loaded.")
    await bot.tree.sync()


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in .env file.")
    else:
        bot.run(DISCORD_TOKEN)
