import discord
from discord import app_commands
from discord.ext import commands
from database import db_manager
from services import game_engine
import typing
import os
from dotenv import load_dotenv

load_dotenv()

# Hardcoded Admin ID (Change this to your Discord ID)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Set in .env: ADMIN_ID=your_id_here

class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.moderators = set()  # Store moderator IDs in memory (TODO: persist to DB)

    async def is_admin_or_owner(self, interaction: discord.Interaction) -> bool:
        """Check if user is bot owner, server owner, or hardcoded admin."""
        user_id = interaction.user.id
        guild_owner_id = interaction.guild.owner_id if interaction.guild else None
        
        # Check: Bot owner
        app_info = await self.bot.application_info()
        if app_info.owner_id == user_id:
            return True
        
        # Check: Hardcoded admin
        if ADMIN_ID != 0 and ADMIN_ID == user_id:
            return True
        
        # Check: Server owner
        if guild_owner_id and guild_owner_id == user_id:
            return True
        
        # Check: Server admin permission
        if interaction.user.guild_permissions.administrator:
            return True
        
        return False

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
    async def setup_game(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        """Setup config để bot có thể tạo game rooms."""
        await interaction.response.defer()
        
        # Check permission
        if not await self.is_admin_or_owner(interaction):
            await interaction.followup.send(
                "❌ Bạn không có quyền sử dụng lệnh này. Chỉ Admin, Server Owner, hoặc hardcoded Admin mới có thể dùng.",
                ephemeral=True
            )
            return
        
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

    @app_commands.command(name="showdb", description="🔍 [Admin] Hiển thị dữ liệu từ bảng cơ sở dữ liệu.")
    @app_commands.describe(table="Bảng dữ liệu cần xem")
    @app_commands.choices(table=[
        app_commands.Choice(name="active_games", value="active_games"),
        app_commands.Choice(name="players", value="players"),
        app_commands.Choice(name="game_maps", value="game_maps"),
    ])
    async def show_db(self, interaction: discord.Interaction, table: app_commands.Choice[str]):
        """Hiển thị tất cả hàng từ một bảng cơ sở dữ liệu."""
        
        # Check permission
        if not await self.is_admin_or_owner(interaction):
            await interaction.response.send_message(
                "❌ Bạn không có quyền sử dụng lệnh này.",
                ephemeral=True
            )
            return
        
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

    @app_commands.command(name="addmod", description="👮 [Admin] Thêm moderator quản lí bot")
    async def add_moderator(self, interaction: discord.Interaction, user: discord.User):
        """Thêm user vào danh sách moderator."""
        
        # Check permission
        if not await self.is_admin_or_owner(interaction):
            await interaction.response.send_message(
                "❌ Bạn không có quyền sử dụng lệnh này.",
                ephemeral=True
            )
            return
        
        self.moderators.add(user.id)
        await interaction.response.send_message(
            f"✅ Đã thêm {user.mention} vào danh sách moderator!",
            ephemeral=True
        )
        print(f"👮 Moderator added: {user.name} (ID: {user.id})")

    @app_commands.command(name="removemod", description="👮 [Admin] Gỡ moderator")
    async def remove_moderator(self, interaction: discord.Interaction, user: discord.User):
        """Gỡ user khỏi danh sách moderator."""
        
        # Check permission
        if not await self.is_admin_or_owner(interaction):
            await interaction.response.send_message(
                "❌ Bạn không có quyền sử dụng lệnh này.",
                ephemeral=True
            )
            return
        
        if user.id in self.moderators:
            self.moderators.remove(user.id)
            await interaction.response.send_message(
                f"✅ Đã gỡ {user.mention} khỏi danh sách moderator!",
                ephemeral=True
            )
            print(f"👮 Moderator removed: {user.name} (ID: {user.id})")
        else:
            await interaction.response.send_message(
                f"⚠️ {user.mention} không phải là moderator.",
                ephemeral=True
            )

    @app_commands.command(name="modlist", description="👮 [Admin] Xem danh sách moderator")
    async def moderator_list(self, interaction: discord.Interaction):
        """Xem danh sách moderator hiện tại."""
        
        # Check permission
        if not await self.is_admin_or_owner(interaction):
            await interaction.response.send_message(
                "❌ Bạn không có quyền sử dụng lệnh này.",
                ephemeral=True
            )
            return
        
        if not self.moderators:
            await interaction.response.send_message(
                "📋 Không có moderator nào.",
                ephemeral=True
            )
            return
        
        mod_mentions = []
        for mod_id in self.moderators:
            try:
                user = await self.bot.fetch_user(mod_id)
                mod_mentions.append(f"• {user.mention} ({user.name})")
            except:
                mod_mentions.append(f"• ID: {mod_id} (không tìm thấy user)")
        
        content = "👮 **Danh sách Moderator:**\n" + "\n".join(mod_mentions)
        await interaction.response.send_message(content, ephemeral=True)
    
    def is_moderator(self, user_id: int) -> bool:
        """Check if user is a moderator."""
        return user_id in self.moderators


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommands(bot))