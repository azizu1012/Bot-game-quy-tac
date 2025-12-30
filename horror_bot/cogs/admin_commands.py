import discord
from discord import app_commands
from discord.ext import commands
from database import db_manager
from services import game_engine
import typing # Import typing for optional guild

class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("✅ Admin Commands Cog sẵn sàng.")

    @commands.hybrid_command(
        name="sync", 
        description="[Quản Trị] Đồng bộ hóa các lệnh (slash commands) của bot."
    )
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, guild: typing.Optional[discord.Guild]):
        """
        Đồng bộ hóa các slash command với Discord.
        Chỉ chủ sở hữu bot mới có thể dùng lệnh này.
        """
        if guild:
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            msg = f"✅ Đã đồng bộ {len(synced)} lệnh cho máy chủ: {guild.name}"
        else:
            synced = await self.bot.tree.sync()
            msg = f"✅ Đã đồng bộ {len(synced)} lệnh trên toàn cục."

        await ctx.send(msg, ephemeral=True)
        print(msg)
        for cmd in synced:
            print(f"   - /{cmd.name}")

    @app_commands.command(name="setup", description="🔧 [Admin] Setup game room cho server này")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(category="📁 Category để tạo game rooms")
    async def setup_game(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        """Setup config để bot có thể tạo game rooms."""
        await interaction.response.defer()
        
        guild_id = interaction.guild.id
        admin_id = interaction.user.id
        category_id = category.id
        
        print(f"\n🔧 [SETUP] Admin {admin_id} setting up game for guild {guild_id}")
        print(f"   └─ Category: {category.name} (ID: {category_id})")
        
        # Check if already setup
        existing_setup = await db_manager.get_game_setup(guild_id)
        if existing_setup:
            print(f"   ⚠️ Setup đã tồn tại, cập nhật...")
            await db_manager.execute_query(
                "UPDATE game_setups SET category_id = ?, created_by = ? WHERE guild_id = ?",
                (category_id, admin_id, guild_id),
                commit=True
            )
        else:
            print(f"   └─ Creating new setup...")
            await db_manager.execute_query(
                "INSERT INTO game_setups (guild_id, category_id, created_by) VALUES (?, ?, ?)",
                (guild_id, category_id, admin_id),
                commit=True
            )
        
        print(f"✅ [SETUP] Complete!\n")
        await interaction.followup.send(
            f"✅ Setup xong! Bot sẽ tạo game rooms trong category: {category.mention}"
        )

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
        
    @show_db.error
    async def on_admin_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.CheckFailure):
            await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Lỗi: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommands(bot))