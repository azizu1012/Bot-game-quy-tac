import discord
from discord import app_commands
from discord.ext import commands
from database import db_manager
from database.db_manager import setup_database
from services import map_generator, game_engine, background_service, scenario_generator
from cogs.game_ui import GameDashboard, ActionView, PlayerProfileEmbed
import os
import json

class GameCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_ready = False

    @app_commands.command(
        name="newgame", 
        description="🎮 Bắt đầu một trò chơi kinh dí mới với tất cả thành viên muốn tham gia"
    )
    @app_commands.describe(scenario="📍 Chọn kịch bản cho trò chơi")
    @app_commands.choices(scenario=[
        app_commands.Choice(name="🏨 Khách Sạn Bị Nguyền Rủa", value="hotel"),
        app_commands.Choice(name="🏥 Tòa Nhà Tâm Thần Bỏ Hoang", value="hospital"),
    ])
    async def new_game(self, interaction: discord.Interaction, scenario: app_commands.Choice[str]):
        await interaction.response.defer()  # Defer vì sẽ tạo channel mất thời gian
        
        game_id = interaction.channel_id
        host_id = interaction.user.id

        if await db_manager.execute_query("SELECT 1 FROM active_games WHERE channel_id = ? AND is_active = 1", (game_id,), fetchone=True):
            await interaction.followup.send("⚠️ Một trò chơi đang hoạt động trong kênh này. Sử dụng `/endgame` để dừng nó.", ephemeral=True)
            return

        # Xóa game cũ nếu có
        await db_manager.execute_query("DELETE FROM players WHERE game_id = ?", (game_id,), commit=True)
        await db_manager.execute_query("DELETE FROM game_maps WHERE game_id = ?", (game_id,), commit=True)
        await db_manager.execute_query("DELETE FROM active_games WHERE channel_id = ?", (game_id,), commit=True)

        scenario_file = f"data/scenarios/{scenario.value}.json"
        game_map = map_generator.generate_map_structure(scenario_file)
        if not game_map:
            await interaction.followup.send("❌ Lỗi: Không thể tạo bản đồ trò chơi.", ephemeral=True)
            return
        
        # Tạo private channel cho trò chơi
        try:
            private_channel = await interaction.guild.create_text_channel(
                name=f"🕷️-{scenario.value}-game",
                category=None,
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=False)
                },
                reason="Tạo kênh riêng cho trò chơi"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot không có quyền tạo kênh mới. Hãy cấp quyền cho bot.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi tạo kênh: {e}", ephemeral=True)
            return
        
        # Lưu vào database
        await db_manager.execute_query(
            "INSERT INTO active_games (channel_id, private_channel_id, host_id, scenario_type, is_active, current_turn) VALUES (?, ?, ?, ?, 1, 1)",
            (game_id, private_channel.id, host_id, scenario.value), commit=True
        )
        await db_manager.execute_query(
            "INSERT INTO game_maps (game_id, map_data) VALUES (?, ?)",
            (game_id, json.dumps(game_map.to_dict())), commit=True
        )

        # Thêm host vào game
        await self.add_player_to_game(host_id, game_id, game_map.start_node_id)
        
        # Tạo embed thông báo trong kênh chính
        embed = discord.Embed(
            title="🎮 Trò Chơi Kinh Dí Mới Bắt Đầu!",
            description=f"**Kịch Bản:** {scenario.name}\n**Người Dẫn Dắt:** <@{host_id}>",
            color=discord.Color.dark_red()
        )
        embed.add_field(
            name="📢 Thông Báo",
            value=f"Một kênh riêng biệt đã được tạo: {private_channel.mention}\n💀 Hãy gõ `/join` để tham gia vào thế giới kinh dí này!",
            inline=False
        )
        embed.set_footer(text="Chỉ những người chơi mới có thể thấy kênh riêng")
        
        await interaction.followup.send(embed=embed)
        
        # Gửi thông báo vào private channel
        await private_channel.send(f"@here\n🎮 **Trò chơi đang bắt đầu!**\nHãy chờ tất cả mọi người join vào...")
        
        # Generate AI intro cho game
        intro_description = await scenario_generator.generate_turn_intro(scenario.value, 1, 1)
        
        turn_manager = game_engine.game_manager.get_manager(game_id, publish_callback=self.publish_turn_results)
        await turn_manager.start_turn()

        message = await self.update_dashboard(private_channel, scene_description=intro_description)
        if message:
            await db_manager.execute_query(
                "UPDATE active_games SET dashboard_message_id = ? WHERE channel_id = ?",
                (message.id, game_id), commit=True
            )

    @app_commands.command(
        name="join", 
        description="👻 Tham gia trò chơi kinh dí - nhận background ngẫu nhiên và chỉ số riêng"
    )
    async def join_game(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        game_id = interaction.channel_id
        user_id = interaction.user.id

        game = await db_manager.execute_query("SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1", (game_id,), fetchone=True)
        if not game:
            await interaction.followup.send("❌ Không có trò chơi nào đang hoạt động trong kênh này. Hãy sử dụng `/newgame` để tạo trò chơi mới.", ephemeral=True)
            return

        if await db_manager.execute_query("SELECT 1 FROM players WHERE user_id = ? AND game_id = ?", (user_id, game_id), fetchone=True):
            await interaction.followup.send("⚠️ Bạn đã tham gia trò chơi này rồi.", ephemeral=True)
            return

        game_map_data = await db_manager.execute_query("SELECT map_data FROM game_maps WHERE game_id = ?", (game_id,), fetchone=True)
        if not game_map_data or not game_map_data['map_data']:
             await interaction.followup.send("❌ Lỗi: Không thể tải dữ liệu bản đồ cho trò chơi này.", ephemeral=True)
             return

        map_nodes = json.loads(game_map_data['map_data'])
        start_node_id = list(map_nodes.get('nodes', {}).keys())[0] if map_nodes.get('nodes') else None
        
        if not start_node_id:
             await interaction.followup.send("❌ Lỗi: Bản đồ trò chơi bị hỏng hoặc trống.", ephemeral=True)
             return

        # Tạo profile cho người chơi
        profile = await background_service.create_player_profile(game['scenario_type'])
        
        # Thêm người chơi vào game
        await db_manager.execute_query(
            """INSERT INTO players (user_id, game_id, background_id, background_name, background_description, 
                                     hp, sanity, agi, acc, current_location_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, game_id, profile['background_id'], profile['background_name'], 
             profile['background_description'], profile['hp'], profile['sanity'], 
             profile['agi'], profile['acc'], start_node_id), 
            commit=True
        )
        
        # Cấp quyền cho user vào private channel
        private_channel = None
        private_channel_id = game['private_channel_id']
        if private_channel_id:
            private_channel = self.bot.get_channel(private_channel_id)
            if private_channel:
                user = interaction.user
                await private_channel.set_permissions(
                    user,
                    read_messages=True,
                    send_messages=False
                )
        
        # Gửi profile embed cho user trong private channel
        profile_embed = PlayerProfileEmbed(
            player_name=interaction.user.display_name,
            background_name=profile['background_name'],
            background_description=profile['background_description'],
            hp=profile['hp'],
            sanity=profile['sanity'],
            agi=profile['agi'],
            acc=profile['acc']
        )
        
        if private_channel:
            await private_channel.send(f"{interaction.user.mention}", embed=profile_embed)
            await private_channel.send("@here")
            await self.update_player_status_board(private_channel, game_id)
        
        # Thông báo trong kênh chính
        embed = discord.Embed(
            title="✅ Tham Gia Thành Công!",
            description=f"{interaction.user.mention} đã bước vào thế giới kinh dí...",
            color=discord.Color.green()
        )
        embed.add_field(name="Background", value=profile['background_name'], inline=True)
        embed.add_field(name="HP", value=str(profile['hp']), inline=True)
        embed.add_field(name="Sanity", value=str(profile['sanity']), inline=True)
        
        await interaction.followup.send(embed=embed)

    async def add_player_to_game(self, user_id, game_id, start_location_id):
        """Helper để thêm người chơi (dùng cho host)."""
        background = {"id": "athlete", "name": "Vận Động Viên", "stats": {"hp": 110, "sanity": 100, "agi": 70, "acc": 50}}
        await db_manager.execute_query(
            """INSERT INTO players (user_id, game_id, background_id, background_name, hp, sanity, agi, acc, current_location_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, game_id, background['id'], background['name'], background['stats']['hp'], 
             background['stats']['sanity'], background['stats']['agi'], background['stats']['acc'], 
             start_location_id), 
            commit=True
        )

    async def publish_turn_results(self, game_id: int, summary: str, turn_events: list[str]):
        game = await db_manager.execute_query("SELECT private_channel_id FROM active_games WHERE channel_id = ?", (game_id,), fetchone=True)
        if not game or not game['private_channel_id']: 
            return
        
        channel = self.bot.get_channel(game['private_channel_id'])
        if not channel: 
            return
        
        full_description = f"{summary}\n\n" + "\n".join(f"- {event}" for event in turn_events)
        await self.update_dashboard(channel, scene_description=full_description)

    async def update_player_status_board(self, channel: discord.TextChannel, game_id: int):
        """Cập nhật bảng hiển thị status của tất cả player."""
        players = await db_manager.execute_query("SELECT * FROM players WHERE game_id = ?", (game_id,), fetchall=True)
        
        status_text = "**📊 TRẠNG THÁI CÁC NGƯỜI CHƠI:**\n\n"
        for p in players:
            status_text += f"👤 **{p['background_name']}** | HP: {p['hp']} | Sanity: {p['sanity']}\n"
        
        await channel.send(status_text)

    async def update_dashboard(self, channel: discord.TextChannel, scene_description: str = "Tình hình căng thẳng...") -> discord.Message | None:
        game = await db_manager.execute_query("SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1", (channel.id,), fetchone=True)
        if not game: 
            # Thử lấy game theo private channel id
            game = await db_manager.execute_query("SELECT * FROM active_games WHERE private_channel_id = ? AND is_active = 1", (channel.id,), fetchone=True)
        if not game: 
            return

        # game_id luôn là channel_id (chính kênh chat của trò chơi)
        game_id = game['channel_id']
        players = await db_manager.execute_query("SELECT * FROM players WHERE game_id = ?", (game_id,), fetchall=True)
        
        player_statuses = []
        for p in players:
            user = self.bot.get_user(p['user_id']) or await self.bot.fetch_user(p['user_id'])
            if user:
                player_statuses.append({
                    'name': p['background_name'], 
                    'hp': p['hp'], 
                    'sanity': p['sanity'], 
                    'has_acted': p['has_acted_this_turn']
                })

        dashboard = GameDashboard(scene_description=scene_description, players_status=player_statuses, turn=game['current_turn'])
        view = ActionView(game_id=game_id)
        
        message_id = game['dashboard_message_id']
        message = None
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=dashboard, view=view)
            except discord.NotFound:
                message = None 

        if not message:
            message = await channel.send(embed=dashboard, view=view)
            await db_manager.execute_query("UPDATE active_games SET dashboard_message_id = ? WHERE channel_id = ?", (message.id, game_id), commit=True)
        
        return message

async def setup(bot: commands.Bot):
    await bot.add_cog(GameCommands(bot))