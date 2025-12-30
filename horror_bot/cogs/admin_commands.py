# -*- coding: utf-8 -*-
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

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """Check if user is the hardcoded admin (ADMIN_ID from .env)."""
        user_id = interaction.user.id
        return ADMIN_ID != 0 and ADMIN_ID == user_id
    
    async def is_admin_or_moderator(self, interaction: discord.Interaction) -> bool:
        """Check if user is admin or moderator."""
        user_id = interaction.user.id
        is_admin = ADMIN_ID != 0 and ADMIN_ID == user_id
        is_mod = user_id in self.moderators
        return is_admin or is_mod

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
        
        # Check permission - ONLY hardcoded ADMIN_ID
        if not await self.is_admin(interaction):
            await interaction.followup.send(
                f"❌ Bạn không có quyền sử dụng lệnh này. Chỉ Admin ID {ADMIN_ID} mới có thể dùng.",
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
        
        # Check permission - Admin only
        if not await self.is_admin(interaction):
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
        
        # Check permission - Admin only
        if not await self.is_admin(interaction):
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
        
        # Check permission - Admin only
        if not await self.is_admin(interaction):
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
        
        # Check permission - Admin only
        if not await self.is_admin(interaction):
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
    
    @app_commands.command(name="forcestop", description="⛔ [Admin/Mod] Cưỡng chế đóng một game")
    async def force_stop_game(self, interaction: discord.Interaction):
        """Cưỡng chế đóng một trò chơi với menu chọn (chỉ Admin hoặc Moderator)."""
        await interaction.response.defer()
        
        # Check permission - Admin or Moderator only
        if not await self.is_admin_or_moderator(interaction):
            await interaction.followup.send(
                "❌ Bạn không có quyền sử dụng lệnh này. Chỉ Admin hoặc Moderator mới được dùng.",
                ephemeral=True
            )
            return
        
        # Get all active games
        games = await db_manager.execute_query(
            "SELECT channel_id, game_code, scenario_type, host_id FROM active_games WHERE is_active = 1",
            fetchall=True
        )
        
        if not games:
            await interaction.followup.send("❌ Không có game nào đang chạy!", ephemeral=True)
            return
        
        # Create select menu with all games
        class GameSelect(discord.ui.View):
            def __init__(self_view):
                super().__init__(timeout=60)
                
                options = [
                    discord.SelectOption(
                        label=f"{game['game_code']} ({game['scenario_type']})",
                        value=game['channel_id'],
                        description=f"Host: <@{game['host_id']}>"
                    )
                    for game in games[:25]  # Discord limit: 25 options
                ]
                
                select = discord.ui.Select(
                    placeholder="Chọn game để tắt...",
                    options=options
                )
                select.callback = self_view.select_callback
                self_view.add_item(select)
            
            async def select_callback(self_view, select_interaction: discord.Interaction):
                game_id = select_interaction.data['values'][0]
                await select_interaction.response.defer()
                
                # Get game details
                game = await db_manager.execute_query(
                    "SELECT game_code, lobby_channel_id, dashboard_channel_id FROM active_games WHERE channel_id = ?",
                    (game_id,),
                    fetchone=True
                )
                
                user_name = interaction.user.name
                is_admin = await self.is_admin(interaction)
                role = "Admin" if is_admin else "Moderator"
                
                print(f"\n⛔ [FORCESTOP] {role} {user_name} (ID: {interaction.user.id}) stopped game {game['game_code']}")
                
                try:
                    # Get all players and delete their private channels
                    players = await db_manager.execute_query(
                        "SELECT private_channel_id FROM players WHERE game_id = ?",
                        (game_id,),
                        fetchall=True
                    )
                    
                    for player in players:
                        if player['private_channel_id']:
                            try:
                                channel = self.bot.get_channel(int(player['private_channel_id']))
                                if channel:
                                    await channel.delete(reason=f"Game forcefully stopped by {role} {user_name}")
                            except Exception as e:
                                print(f"   ⚠️ Error deleting private channel: {e}")
                    
                    # Delete lobby and dashboard channels
                    for channel_id in [game['lobby_channel_id'], game['dashboard_channel_id']]:
                        if channel_id:
                            try:
                                channel = self.bot.get_channel(int(channel_id))
                                if channel:
                                    await channel.delete(reason=f"Game forcefully stopped by {role} {user_name}")
                            except Exception as e:
                                print(f"   ⚠️ Error deleting channel: {e}")
                    
                    # Delete from database
                    await db_manager.execute_query(
                        "DELETE FROM players WHERE game_id = ?",
                        (game_id,),
                        commit=True
                    )
                    await db_manager.execute_query(
                        "DELETE FROM active_games WHERE channel_id = ?",
                        (game_id,),
                        commit=True
                    )
                    await db_manager.execute_query(
                        "DELETE FROM game_maps WHERE game_id = ?",
                        (game_id,),
                        commit=True
                    )
                    
                    print(f"✅ [FORCESTOP] Game {game['game_code']} deleted!\n")
                    
                    await select_interaction.followup.send(
                        f"✅ Đã cưỡng chế đóng game `{game['game_code']}`!\n"
                        f"👤 Thực hiện bởi: {role} {user_name}",
                        ephemeral=False
                    )
                except Exception as e:
                    print(f"❌ Error in forcestop: {e}")
                    await select_interaction.followup.send(
                        f"❌ Lỗi khi cưỡng chế đóng game: {e}",
                        ephemeral=True
                    )
        
        await interaction.followup.send(
            "⛔ **Chọn game để tắt:**",
            view=GameSelect(),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommands(bot))