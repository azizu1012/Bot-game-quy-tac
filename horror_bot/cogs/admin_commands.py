import discord
from discord import app_commands
from discord.ext import commands
from database import db_manager
from services import game_engine

class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Admin Commands Cog is ready.")

    @app_commands.command(name="endgame", description="[Admin] Forcibly ends the game in this channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def end_game(self, interaction: discord.Interaction):
        """Forcibly ends a game and cleans up the database."""
        game_id = interaction.channel_id
        
        active_game = await db_manager.execute_query("SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1", (game_id,), fetchone=True)
        if not active_game:
            await interaction.response.send_message("There is no active game to end in this channel.", ephemeral=True)
            return

        # Clean up the game manager instance to stop any running tasks
        game_engine.game_manager.end_game(game_id)

        # Delete all related data
        await db_manager.execute_query("DELETE FROM players WHERE game_id = ?", (game_id,), commit=True)
        await db_manager.execute_query("DELETE FROM game_maps WHERE game_id = ?", (game_id,), commit=True)
        await db_manager.execute_query("DELETE FROM active_games WHERE channel_id = ?", (game_id,), commit=True)

        await interaction.response.send_message("The game has been forcibly ended and all data has been cleared.", ephemeral=False)

    @app_commands.command(name="showdb", description="[Admin] Shows raw data from a database table.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(table="The table to show data from.")
    @app_commands.choices(table=[
        app_commands.Choice(name="active_games", value="active_games"),
        app_commands.Choice(name="players", value="players"),
        app_commands.Choice(name="game_maps", value="game_maps"),
    ])
    async def show_db(self, interaction: discord.Interaction, table: app_commands.Choice[str]):
        """Displays all rows from a specified database table."""
        
        # A simple security check to prevent arbitrary table access
        allowed_tables = ["active_games", "players", "game_maps"]
        if table.value not in allowed_tables:
            await interaction.response.send_message("Invalid table specified.", ephemeral=True)
            return

        data = await db_manager.execute_query(f"SELECT * FROM {table.value}", fetchall=True)
        
        if not data:
            await interaction.response.send_message(f"No data found in table `{table.name}`.", ephemeral=True)
            return
            
        response_content = f"### Data from `{table.name}`:\n"
        response_content += "```json\n"
        # Convert rows to dictionaries for clean printing
        rows_as_dicts = [dict(row) for row in data]
        import json
        response_content += json.dumps(rows_as_dicts, indent=2)
        response_content += "\n```"
        
        if len(response_content) > 1900:
             response_content = response_content[:1900] + "\n... (truncated)"

        await interaction.response.send_message(response_content, ephemeral=True)
        
    @end_game.error
    @show_db.error
    async def on_admin_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.CheckFailure):
            await interaction.response.send_message("You do not have the required permissions for this command.", ephemeral=True)
        else:
            await interaction.response.send_message(f"An unexpected error occurred: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommands(bot))