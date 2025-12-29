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

    @app_commands.command(name="endgame", description="🛑 [Quản Trị] Kết thúc trò chơi đang hoạt động và xóa dữ liệu.")
    @app_commands.checks.has_permissions(administrator=True)
    async def end_game(self, interaction: discord.Interaction):
        """Kết thúc một trò chơi và xóa dữ liệu."""
        game_id = interaction.channel_id
        
        active_game = await db_manager.execute_query("SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1", (game_id,), fetchone=True)
        if not active_game:
            await interaction.response.send_message("⚠️ Không có trò chơi đang hoạt động để kết thúc trong kênh này.", ephemeral=True)
            return

        # Clean up the game manager instance to stop any running tasks
        game_engine.game_manager.end_game(game_id)

        # Delete private channel if exists
        if active_game['private_channel_id']:
            try:
                private_channel = self.bot.get_channel(active_game['private_channel_id'])
                if private_channel:
                    await private_channel.delete(reason="Game ended")
            except discord.Forbidden:
                pass  # Bot không có quyền xóa

        # Delete all related data
        await db_manager.execute_query("DELETE FROM players WHERE game_id = ?", (game_id,), commit=True)
        await db_manager.execute_query("DELETE FROM game_maps WHERE game_id = ?", (game_id,), commit=True)
        await db_manager.execute_query("DELETE FROM active_games WHERE channel_id = ?", (game_id,), commit=True)

        await interaction.response.send_message("✅ Trò chơi đã kết thúc! Kênh riêng đã bị xóa và dữ liệu đã bị xóa.", ephemeral=False)

    @app_commands.command(name="showdb", description="🔍 [Quản Trị] Hiển thị dữ liệu từ bảng cơ sở dữ liệu.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(table="Bảng dữ liệu cần xem")
    @app_commands.choices(table=[
        app_commands.Choice(name="active_games", value="active_games"),
        app_commands.Choice(name="players", value="players"),
        app_commands.Choice(name="game_maps", value="game_maps"),
    ])
    async def show_db(self, interaction: discord.Interaction, table: app_commands.Choice[str]):
        """Hiển thị tất cả hàng từ một bảng cơ sở dữ liệu."""
        
        # A simple security check to prevent arbitrary table access
        allowed_tables = ["active_games", "players", "game_maps"]
        if table.value not in allowed_tables:
            await interaction.response.send_message("Bảng không hợp lệ.", ephemeral=True)
            return

        data = await db_manager.execute_query(f"SELECT * FROM {table.value}", fetchall=True)
        
        if not data:
            await interaction.response.send_message(f"Không tìm thấy dữ liệu trong bảng `{table.name}`.", ephemeral=True)
            return
            
        response_content = f"### Dữ liệu từ `{table.name}`:\n"
        response_content += "```json\n"
        # Convert rows to dictionaries for clean printing
        rows_as_dicts = [dict(row) for row in data]
        import json
        response_content += json.dumps(rows_as_dicts, indent=2, ensure_ascii=False)
        response_content += "\n```"
        
        if len(response_content) > 1900:
             response_content = response_content[:1900] + "\n... (bị cắt ngắn)"

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