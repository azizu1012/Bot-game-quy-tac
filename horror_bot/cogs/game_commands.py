"""
HORROR BOT - GAME COMMANDS (Free-Form Text Actions)
3-tier channel architecture: Lobby + Dashboard + Private Per-User
"""

import discord
from discord import app_commands
from discord.ext import commands
from database import db_manager
from services import game_engine, map_generator, scenario_generator, llm_service, background_service
import json
import asyncio
import random
import uuid


class GameCommands(commands.Cog):
    """Game commands with 3-tier channel architecture."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="newgame",
        description="🎮 Tạo một phòng chơi mới (3-tier channels: lobby + dashboard + private)"
    )
    @app_commands.describe(scenario="📍 Chọn kịch bản (để trống = random)")
    async def new_game(self, interaction: discord.Interaction, scenario: str = None):
        """Create new game with 3-tier channel structure."""
        await interaction.response.defer()
        print(f"\n🎮 [NEW_GAME] User {interaction.user.id} starting new game...")

        # ✅ CHECK: Verify admin setup
        guild_setup = await db_manager.get_game_setup(interaction.guild.id)
        if not guild_setup:
            await interaction.followup.send(
                "❌ Admin chưa setup Category cho game!\n"
                "📌 Hãy yêu cầu Admin chạy: `/setup [category_name]`",
                ephemeral=True
            )
            return

        # Check if user already in game
        current_game = await db_manager.get_player_current_game(interaction.user.id)
        if current_game:
            await interaction.followup.send(
                "⚠️ Bạn đang tham gia một trò chơi khác!",
                ephemeral=True
            )
            return

        # Generate game code
        game_code = str(uuid.uuid4())[:8].upper()
        print(f"   └─ Game code: {game_code}")

        # Random scenario
        if scenario is None:
            scenarios = ["asylum", "factory", "ghost_village", "cursed_mansion", "mine", "prison", 
                        "abyss", "dead_forest", "research_hospital", "ghost_ship"]
            scenario_value = random.choice(scenarios)
        else:
            scenario_value = scenario
        print(f"   └─ Scenario: {scenario_value}")

        # Get game ID (use a unique ID, not channel_id)
        game_id = str(uuid.uuid4())[:12]
        print(f"   └─ Game ID: {game_id}")

        # Load scenario map
        print(f"   └─ Loading scenario map...")
        scenario_file = f"data/scenarios/{scenario_value}.json"
        game_map = map_generator.generate_map_structure(scenario_file)
        if not game_map:
            await interaction.followup.send("❌ Lỗi: Không thể tạo bản đồ.", ephemeral=True)
            return

        # Create 3-tier channel structure
        print(f"   └─ Creating 3-tier channels...")
        try:
            category = interaction.guild.get_channel(guild_setup['category_id'])
            if not category or not isinstance(category, discord.CategoryChannel):
                await interaction.followup.send(
                    "❌ Category không tồn tại hoặc đã bị xóa.",
                    ephemeral=True
                )
                return

            # TIER 1: Lobby channel
            lobby_channel = await interaction.guild.create_text_channel(
                name=f"game-lobby-{random.randint(1000, 9999)}",
                category=category,
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=False)
                },
                reason="Game lobby (lore + start button)"
            )
            print(f"      ✅ Lobby created: #{lobby_channel.name}")

            # TIER 2: Dashboard channel (read-only)
            dashboard_channel = await interaction.guild.create_text_channel(
                name=f"game-dashboard-{random.randint(1000, 9999)}",
                category=category,
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                    self.bot.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                },
                reason="Game dashboard (real-time stats, read-only)"
            )
            print(f"      ✅ Dashboard created: #{dashboard_channel.name}")

        except discord.Forbidden:
            await interaction.followup.send("❌ Bot không có quyền tạo kênh.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi tạo kênh: {e}", ephemeral=True)
            return

        # Save to database
        print(f"   └─ Saving to database...")
        await db_manager.execute_query(
            """INSERT INTO active_games 
               (channel_id, lobby_channel_id, dashboard_channel_id, host_id, 
                game_creator_id, scenario_type, game_code, setup_by_admin_id, is_active) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (game_id, lobby_channel.id, dashboard_channel.id, interaction.user.id,
             interaction.user.id, scenario_value, game_code, guild_setup['created_by']),
            commit=True
        )

        # Save map
        await db_manager.execute_query(
            "INSERT INTO game_maps (game_id, map_data) VALUES (?, ?)",
            (game_id, json.dumps(game_map.to_dict())),
            commit=True
        )

        # Initialize game context
        await db_manager.execute_query(
            """INSERT INTO game_context (game_id, scenario_type, current_threat_level) 
               VALUES (?, ?, 0)""",
            (game_id, scenario_value),
            commit=True
        )

        # Add creator as first player
        await self._add_player_to_game(interaction.user.id, game_id, game_map.start_node_id, scenario_value)

        # Send lore to lobby
        print(f"   └─ Generating scenario lore...")
        greeting = await llm_service.generate_simple_greeting(scenario_value)
        
        embed = discord.Embed(
            title=f"📖 {scenario_value.upper()}",
            description=greeting,
            color=discord.Color.dark_red()
        )
        embed.set_footer(text=f"Mã Phòng: {game_code}")

        # Create start button
        class StartGameButton(discord.ui.View):
            def __init__(btn_self):
                super().__init__(timeout=None)

            @discord.ui.button(label="🎮 BẮT ĐẦU", style=discord.ButtonStyle.success)
            async def start_button(btn_self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                await btn_interaction.response.defer()
                await self._start_game_for_player(btn_interaction, game_id, scenario_value)

        await lobby_channel.send(embed=embed, view=StartGameButton())
        print(f"      ✅ Lore sent to lobby")

        # Notify in main channel
        await interaction.followup.send(
            f"🎮 **Phòng Mới!** {lobby_channel.mention}\n"
            f"📊 Dashboard: {dashboard_channel.mention}\n"
            f"Kịch Bản: `{scenario_value}`\n"
            f"Mã Phòng: `{game_code}`"
        )
        print(f"✅ [NEW_GAME] Complete!\n")

    async def _add_player_to_game(self, user_id: int, game_id: str, start_location_id: str, scenario_type: str):
        """Add player to game with default profile."""
        profile = await background_service.create_player_profile(scenario_type)
        
        await db_manager.execute_query(
            """INSERT INTO players 
               (user_id, game_id, background_id, background_name, background_description,
                hp, sanity, agi, acc, current_location_id, is_ready)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (user_id, game_id, profile['background_id'], profile['background_name'],
             profile['background_description'], profile['hp'], profile['sanity'],
             profile['agi'], profile['acc'], start_location_id),
            commit=True
        )
        print(f"      ✅ Player {user_id} added to game {game_id}")

    async def _start_game_for_player(self, interaction: discord.Interaction, game_id: str, scenario_type: str):
        """Create private channel for player when they click START button."""
        user_id = interaction.user.id
        
        # Check if already started
        player = await db_manager.execute_query(
            "SELECT is_ready FROM players WHERE user_id = ? AND game_id = ?",
            (user_id, game_id),
            fetchone=True
        )
        
        if not player:
            await interaction.followup.send("❌ Bạn chưa join game này!", ephemeral=True)
            return

        if player['is_ready']:
            await interaction.followup.send("⚠️ Bạn đã start game rồi!", ephemeral=True)
            return

        # Get game and player info
        game = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE channel_id = ?",
            (game_id,),
            fetchone=True
        )
        
        if not game:
            await interaction.followup.send("❌ Game không tồn tại!", ephemeral=True)
            return

        # Create private channel for this player
        print(f"   └─ Creating private channel for player {user_id}...")
        try:
            guild = interaction.guild
            category = guild.get_channel(game['lobby_channel_id']).category
            
            player_name = interaction.user.display_name.replace(" ", "-").lower()[:20]
            private_channel = await guild.create_text_channel(
                name=f"private-{player_name}-{random.randint(100, 999)}",
                category=category,
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    self.bot.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                },
                reason=f"Private game channel for {interaction.user.name}"
            )
            print(f"      ✅ Private channel created: #{private_channel.name}")
            
            # Save private channel ID
            await db_manager.execute_query(
                "UPDATE players SET private_channel_id = ?, is_ready = 1 WHERE user_id = ? AND game_id = ?",
                (private_channel.id, user_id, game_id),
                commit=True
            )
            
            # Send welcome message to private channel
            player_data = await db_manager.execute_query(
                "SELECT background_name, hp, sanity, agi, acc, current_location_id FROM players WHERE user_id = ? AND game_id = ?",
                (user_id, game_id),
                fetchone=True
            )
            
            welcome_text = f"""🎮 **Chào mừng đến {scenario_type.upper()}!**

👤 **Nhân vật:** {player_data['background_name']}
❤️ **HP:** {player_data['hp']}
🧠 **Sanity:** {player_data['sanity']}
⚡ **AGI:** {player_data['agi']} | 🎯 **ACC:** {player_data['acc']}

📝 **Hướng dẫn:**
Gõ các hành động tự do vào đây. Ví dụ:
- "Tôi rón rén mở cánh cửa bên trái"
- "Tôi lấy chiếc đèn pin trên tường"
- "Tôi nghe từng tiếng động"

LLM sẽ phân tích hành động của bạn và cập nhật kịch bản!"""

            await private_channel.send(welcome_text)
            
            # Send initial scene (from LLM)
            game_map = json.loads((await db_manager.execute_query(
                "SELECT map_data FROM game_maps WHERE game_id = ?",
                (game_id,),
                fetchone=True
            ))['map_data'])
            
            current_room_id = player_data['current_location_id']
            current_room = game_map['nodes'].get(current_room_id, {})
            
            initial_scene = f"""**📍 {current_room.get('room_type', 'Room').upper()}**

{current_room.get('description', 'Một không gian bí ẩn...')}

💭 *Bạn cảm thấy sợ hãi nhưng cũng tò mò...* 

**Hãy mô tả hành động của bạn tiếp theo!**"""

            await private_channel.send(initial_scene)
            
            # Message to user
            await interaction.followup.send(
                f"✅ Game started! Check {private_channel.mention}",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"❌ Error creating private channel: {e}")
            await interaction.followup.send(f"❌ Lỗi: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for player actions in private channels."""
        # Ignore bot messages
        if message.author == self.bot.user:
            return
        
        # Ignore messages outside private channels
        if not message.channel.name.startswith("private-"):
            return
        
        # Find game_id from private channel
        player_id = message.author.id
        player = await db_manager.execute_query(
            "SELECT game_id FROM players WHERE user_id = ? AND private_channel_id = ?",
            (player_id, message.channel.id),
            fetchone=True
        )
        
        if not player:
            return
        
        game_id = player['game_id']
        print(f"[ACTION] Player {player_id} in game {game_id}: {message.content}")
        
        # Process free-form action through game engine
        await game_engine.process_free_text_action(
            player_id=player_id,
            game_id=game_id,
            action_text=message.content,
            channel=message.channel,
            bot=self.bot
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(GameCommands(bot))
