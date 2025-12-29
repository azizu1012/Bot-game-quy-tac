import discord
from discord.ext import commands
from services import game_engine
from database import db_manager

# --- UI Views (Buttons) ---

class ActionView(discord.ui.View):
    def __init__(self, game_id: int):
        super().__init__(timeout=None) # Persistent view
        self.game_id = game_id

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.danger, custom_id="attack_button")
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Acknowledge the action ephemerally
        await interaction.response.send_message("You chose to Attack! Waiting for others...", ephemeral=True)
        # Register the action with the game engine
        await game_engine.register_action(interaction.user.id, self.game_id, "attack")

    @discord.ui.button(label="🏃 Flee", style=discord.ButtonStyle.secondary, custom_id="flee_button")
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("You chose to Flee! Waiting for others...", ephemeral=True)
        await game_engine.register_action(interaction.user.id, self.game_id, "flee")

    @discord.ui.button(label="🔍 Search", style=discord.ButtonStyle.primary, custom_id="search_button")
    async def search(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("You chose to Search the area! Waiting for others...", ephemeral=True)
        await game_engine.register_action(interaction.user.id, self.game_id, "search")


# --- UI Embeds (Display) ---

def create_progress_bar(value: int, max_value: int, length: int = 10) -> str:
    """Creates a simple text-based progress bar."""
    ratio = value / max_value
    filled_length = int(length * ratio)
    bar = '█' * filled_length + '░' * (length - filled_length)
    return f"[{bar}] {value}/{max_value}"

class GameDashboard(discord.Embed):
    """A custom Embed to display the game's state."""
    def __init__(self, scene_description: str, players_status: list, turn: int):
        super().__init__(
            title=f"Turn {turn}",
            description=f"```{{scene_description}}```",
            color=discord.Color.dark_red()
        )
        self.set_author(name="Cursed Chronicles")
        
        status_text = ""
        for player in players_status:
            hp_bar = create_progress_bar(player['hp'], 100)
            sanity_bar = create_progress_bar(player['sanity'], 100)
            acted_emoji = "✅" if player['has_acted'] else "⏳"
            status_text += f"{acted_emoji} **{player['name']}**\n"
            status_text += f"❤️ HP: {hp_bar}\n"
            status_text += f"🧠 Sanity: {sanity_bar}\n\n"
            
        if not status_text:
            status_text = "No players in the game."

        self.add_field(name="Player Status", value=status_text, inline=False)
        self.set_footer(text="Choose your action below.")


# --- Cog for loading the persistent view ---

class GameUICog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Game UI Cog is ready.")
        # Load all active game views from database
        await self.load_active_game_views()

    async def load_active_game_views(self):
        """Load ActionView for all active games from database."""
        active_games = await db_manager.execute_query(
            "SELECT channel_id FROM active_games WHERE is_active = 1",
            fetchall=True
        )
        if active_games:
            for game in active_games:
                game_id = game['channel_id']
                self.bot.add_view(ActionView(game_id=game_id))
                print(f"✅ Loaded ActionView for game {game_id}")

async def setup(bot: commands.Bot):
    await bot.add_cog(GameUICog(bot))