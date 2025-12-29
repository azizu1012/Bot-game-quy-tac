import discord
from discord import app_commands
from discord.ext import commands
from database import db_manager
from services import map_generator, game_engine, background_service, scenario_generator, llm_service
from cogs.game_ui import ACTION_EMOJIS
from config import THINKING_PHASE_SECONDS, TURN_TIME_SECONDS
import json
import asyncio
import random
import time

class WaitingRoomView(discord.ui.View):
    """Waiting room confirmation buttons."""
    def __init__(self, game_id: int, timeout: float = None):
        super().__init__(timeout=timeout)
        self.game_id = game_id

    @discord.ui.button(label="✅ Xác Nhận Tham Gia", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_id = interaction.user.id
        
        # Mark player as confirmed in waiting room
        await db_manager.execute_query(
            "UPDATE players SET waiting_room_confirmed = 1 WHERE user_id = ? AND game_id = ?",
            (user_id, self.game_id),
            commit=True
        )
        
        await interaction.followup.send(
            f"✅ {interaction.user.mention} đã xác nhận tham gia!",
            ephemeral=False,
            delete_after=3
        )

    @discord.ui.button(label="❌ Từ Chối Tham Gia", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject_join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_id = interaction.user.id
        game_id = self.game_id
        
        # Remove player from game
        await db_manager.execute_query(
            "DELETE FROM players WHERE user_id = ? AND game_id = ?",
            (user_id, game_id),
            commit=True
        )
        
        # Give permission back to private channel
        game = await db_manager.execute_query(
            "SELECT private_channel_id FROM active_games WHERE channel_id = ?",
            (game_id,),
            fetchone=True
        )
        
        if game and game['private_channel_id']:
            channel = interaction.client.get_channel(game['private_channel_id'])
            if channel:
                try:
                    await channel.set_permissions(interaction.user, overwrite=None)
                except:
                    pass
        
        await interaction.followup.send(
            f"❌ {interaction.user.mention} đã từ chối tham gia phòng chờ!",
            ephemeral=False,
            delete_after=3
        )


class GameCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_ready = False
        self.waiting_room_updates = {}  # Track waiting room message updates

    @app_commands.command(
        name="newgame",
        description="🎮 Bắt đầu một trò chơi kinh dí mới"
    )
    @app_commands.describe(scenario="📍 Chọn kịch bản (để trống để random)")
    async def new_game(self, interaction: discord.Interaction, scenario: str = None):
        await interaction.response.defer()

        # Check if user is already in another game
        current_game = await db_manager.get_player_current_game(interaction.user.id)
        if current_game:
            await interaction.followup.send(
                "⚠️ Bạn đang tham gia một trò chơi khác! Hãy kết thúc nó trước (`/endgame`).",
                ephemeral=True
            )
            return

        # Random scenario if not specified
        if scenario is None:
            scenarios = ["asylum", "factory", "ghost_village", "cursed_mansion", "mine", "prison", "abyss", "dead_forest", "research_hospital", "ghost_ship"]
            scenario_value = random.choice(scenarios)
        else:
            scenario_value = scenario

        game_id = interaction.channel_id
        host_id = interaction.user.id

        # Check if game already exists
        if await db_manager.execute_query(
            "SELECT 1 FROM active_games WHERE channel_id = ? AND is_active = 1",
            (game_id,),
            fetchone=True
        ):
            await interaction.followup.send(
                "⚠️ Một trò chơi đang hoạt động trong kênh này.",
                ephemeral=True
            )
            return

        # Clean old game data
        await db_manager.execute_query("DELETE FROM players WHERE game_id = ?", (game_id,), commit=True)
        await db_manager.execute_query("DELETE FROM game_maps WHERE game_id = ?", (game_id,), commit=True)
        await db_manager.execute_query("DELETE FROM active_games WHERE channel_id = ?", (game_id,), commit=True)

        # Load scenario
        scenario_file = f"data/scenarios/{scenario_value}.json"
        game_map = map_generator.generate_map_structure(scenario_file)
        if not game_map:
            await interaction.followup.send("❌ Lỗi: Không thể tạo bản đồ.", ephemeral=True)
            return

        # Create private channel
        try:
            private_channel = await interaction.guild.create_text_channel(
                name=f"phong-choi-{random.randint(1, 999)}",  # Generic name: phong-choi-[number]
                category=None,
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=False)
                },
                reason="Tạo kênh riêng cho trò chơi"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot không có quyền tạo kênh.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}", ephemeral=True)
            return

        # Save game to database
        await db_manager.execute_query(
            """INSERT INTO active_games 
               (channel_id, private_channel_id, host_id, game_creator_id, scenario_type, is_active, 
                current_turn, waiting_room_stage) 
               VALUES (?, ?, ?, ?, ?, 1, 1, 1)""",
            (game_id, private_channel.id, host_id, host_id, scenario_value),
            commit=True
        )
        await db_manager.execute_query(
            "INSERT INTO game_maps (game_id, map_data) VALUES (?, ?)",
            (game_id, json.dumps(game_map.to_dict())),
            commit=True
        )

        # Add host as first player
        await self.add_player_to_game(host_id, game_id, game_map.start_node_id)

        # Notify in main channel
        await interaction.followup.send(
            f"🎮 **Trò chơi mới!** {private_channel.mention}\n"
            f"Kịch bản: {scenario_value}\n"
            f"💀 Gõ `/join` để tham gia!"
        )

        # Send waiting room message in private channel
        dark_rules = await llm_service.generate_dark_rules(scenario_value)
        waiting_greeting = await llm_service.generate_waiting_room_message(1, 8)

        waiting_message = f"""**━━━━━━━━━━━━━━━━━━━**
{waiting_greeting}

**📜 QUY TẮC QUỶ DỊ CỦA THẾ GIỚI NÀY:**
{dark_rules}

**Đang chờ xác nhận: 1/8**
Nhấn ✅ để xác nhận tham gia trò chơi!
Nhấn ❌ để từ chối rời phòng.

Nếu bạn vô tình ấn ❌, bạn vẫn có thể `/join` lại nếu phòng chưa bắt đầu.
**━━━━━━━━━━━━━━━━━━━**"""

        view = WaitingRoomView(game_id)
        msg = await private_channel.send(waiting_message, view=view)
        
        await db_manager.execute_query(
            "UPDATE active_games SET waiting_room_message_id = ? WHERE channel_id = ?",
            (msg.id, game_id),
            commit=True
        )

    @app_commands.command(
        name="join",
        description="👻 Tham gia trò chơi"
    )
    async def join_game(self, interaction: discord.Interaction):
        await interaction.response.defer()

        game_id = interaction.channel_id
        user_id = interaction.user.id

        # Check if user is already in another game
        current_game = await db_manager.get_player_current_game(user_id)
        if current_game and current_game != game_id:
            await interaction.followup.send(
                "⚠️ Bạn đang tham gia một trò chơi khác! Hãy `/endgame` trước.",
                ephemeral=True
            )
            return

        # Get game info
        game = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1",
            (game_id,),
            fetchone=True
        )
        if not game:
            await interaction.followup.send(
                "❌ Không có trò chơi nào trong kênh này.",
                ephemeral=True
            )
            return

        # Check if already in this game
        if await db_manager.check_player_in_game(user_id, game_id):
            await interaction.followup.send(
                "⚠️ Bạn đã tham gia trò chơi này rồi!",
                ephemeral=True
            )
            return

        # Get map info
        game_map_data = await db_manager.execute_query(
            "SELECT map_data FROM game_maps WHERE game_id = ?",
            (game_id,),
            fetchone=True
        )
        if not game_map_data:
            await interaction.followup.send("❌ Lỗi: Dữ liệu bản đồ bị mất.", ephemeral=True)
            return

        map_nodes = json.loads(game_map_data['map_data'])
        start_node_id = list(map_nodes.get('nodes', {}).keys())[0] if map_nodes.get('nodes') else None
        if not start_node_id:
            await interaction.followup.send("❌ Lỗi: Bản đồ bị hỏng.", ephemeral=True)
            return

        # Create player profile
        profile = await background_service.create_player_profile(game['scenario_type'])

        # Add to database
        await db_manager.execute_query(
            """INSERT INTO players 
               (user_id, game_id, background_id, background_name, background_description,
                hp, sanity, agi, acc, current_location_id, waiting_room_confirmed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (user_id, game_id, profile['background_id'], profile['background_name'],
             profile['background_description'], profile['hp'], profile['sanity'],
             profile['agi'], profile['acc'], start_node_id),
            commit=True
        )

        # Grant private channel access
        private_channel = self.bot.get_channel(game['private_channel_id'])
        if private_channel:
            await private_channel.set_permissions(
                interaction.user,
                read_messages=True,
                send_messages=False
            )

        # Update waiting room message
        if game['waiting_room_stage'] == 1:  # Still in waiting room
            await self.update_waiting_room(private_channel, game_id)

        await interaction.followup.send(
            f"✅ {interaction.user.mention} tham gia với background: **{profile['background_name']}**",
            ephemeral=False,
            delete_after=5
        )

    @app_commands.command(
        name="startgame",
        description="🚀 Bắt đầu trò chơi (sau khi tất cả xác nhận)"
    )
    async def start_game(self, interaction: discord.Interaction):
        await interaction.response.defer()

        game_id = interaction.channel_id
        user_id = interaction.user.id

        # Check if user is game creator
        creator_id = await db_manager.get_game_creator(game_id)
        if user_id != creator_id:
            await interaction.followup.send(
                "❌ Chỉ người tạo game mới có thể bắt đầu trò chơi!",
                ephemeral=True
            )
            return

        game = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1",
            (game_id,),
            fetchone=True
        )
        if not game:
            await interaction.followup.send("❌ Không có trò chơi nào.", ephemeral=True)
            return

        if game['waiting_room_stage'] != 1:
            await interaction.followup.send(
                "⚠️ Trò chơi không ở giai đoạn chờ!",
                ephemeral=True
            )
            return

        # Get confirmation status
        confirmations = await db_manager.get_waiting_room_confirmations(game_id)
        if confirmations['confirmed'] == 0:
            await interaction.followup.send(
                "❌ Không có ai xác nhận! Chờ người chơi xác nhận trước.",
                ephemeral=True
            )
            return

        # Mark game as started
        await db_manager.execute_query(
            "UPDATE active_games SET waiting_room_stage = 2 WHERE channel_id = ?",
            (game_id,),
            commit=True
        )

        # Get private channel
        private_channel = self.bot.get_channel(game['private_channel_id'])
        if not private_channel:
            return

        # Send startup message
        startup_msg = f"""**🎮 TRÒ CHƠI KINH DÍ BẮT ĐẦU!**

Các người chơi đã xác nhận: {confirmations['confirmed']}/{confirmations['total']}

Những người chơi khác (chưa xác nhận) sẽ bị loại khỏi trò chơi.
"""
        await private_channel.send(startup_msg)

        # Remove players who didn't confirm
        for player in confirmations['players']:
            if not player.get('waiting_room_confirmed'):
                await db_manager.execute_query(
                    "DELETE FROM players WHERE user_id = ? AND game_id = ?",
                    (player['user_id'], game_id),
                    commit=True
                )

        # Send initial scene
        intro_description = await scenario_generator.generate_turn_intro(game['scenario_type'], 1, 1)

        # Get all players and format as plain text
        players = await db_manager.execute_query(
            "SELECT user_id, background_name, hp, sanity FROM players WHERE game_id = ?",
            (game_id,),
            fetchall=True
        )

        players_info = "\n".join([
            f"👤 {p['background_name']} | HP: {p['hp']} | Sanity: {p['sanity']}"
            for p in players
        ])

        scene_text = f"""**━━━━━━━━━━━━━━━━━━━**
**LƯỢT 1**

{intro_description}

**📊 CÁC NGƯỜI CHƠI:**
{players_info}

**⏱️ Đang đếm ngược...**
**━━━━━━━━━━━━━━━━━━━**"""

        # Post game message
        game_msg = await private_channel.send(scene_text)

        await db_manager.execute_query(
            "UPDATE active_games SET dashboard_message_id = ? WHERE channel_id = ?",
            (game_msg.id, game_id),
            commit=True
        )

        # Start turn manager
        turn_manager = game_engine.game_manager.get_manager(game_id, publish_callback=self.publish_turn_results)
        await turn_manager.start_turn()

        # Start countdown update task
        asyncio.create_task(self.update_game_countdown(game_msg, game_id, TURN_TIME_SECONDS))

    @app_commands.command(
        name="endgame",
        description="❌ Kết thúc trò chơi"
    )
    async def end_game(self, interaction: discord.Interaction):
        await interaction.response.defer()

        game_id = interaction.channel_id
        user_id = interaction.user.id

        game = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1",
            (game_id,),
            fetchone=True
        )
        if not game:
            await interaction.followup.send("❌ Không có trò chơi nào.", ephemeral=True)
            return

        # Check if user is creator or if voting majority wants to end
        creator_id = await db_manager.get_game_creator(game_id)
        
        if user_id == creator_id:
            # Creator can end immediately
            await self.cleanup_game(game_id)
            await interaction.followup.send("✅ Người tạo game đã kết thúc trò chơi.", ephemeral=False)
        else:
            # Regular player starts a vote
            await interaction.followup.send(
                f"🗳️ {interaction.user.mention} yêu cầu bỏ phiếu kết thúc game.\n"
                "Cần 50%+ đồng ý để kết thúc.\n"
                "(Hoặc chỉ người tạo game mới có thể kết thúc ngay)",
                ephemeral=False
            )

    async def cleanup_game(self, game_id: int):
        """Clean up game from database and delete private channel."""
        game = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1",
            (game_id,),
            fetchone=True
        )
        if not game:
            return

        # Stop game manager
        game_engine.game_manager.end_game(game_id)

        # Mark inactive
        await db_manager.execute_query(
            "UPDATE active_games SET is_active = 0 WHERE channel_id = ?",
            (game_id,),
            commit=True
        )

        # Delete private channel
        if game['private_channel_id']:
            try:
                channel = self.bot.get_channel(game['private_channel_id'])
                if channel:
                    await channel.delete(reason="Game ended")
            except:
                pass

    async def update_waiting_room(self, channel: discord.TextChannel, game_id: int):
        """Update waiting room message with current confirmations."""
        game = await db_manager.execute_query(
            "SELECT waiting_room_message_id FROM active_games WHERE channel_id = ?",
            (game_id,),
            fetchone=True
        )
        if not game or not game['waiting_room_message_id']:
            return

        confirmations = await db_manager.get_waiting_room_confirmations(game_id)
        total_confirmed = confirmations['confirmed']
        total_players = confirmations['total']

        try:
            msg = await channel.fetch_message(game['waiting_room_message_id'])
            waiting_msg = f"""**━━━━━━━━━━━━━━━━━━━**
Đang chờ tất cả người chơi xác nhận...

**Đã xác nhận: {total_confirmed}/{total_players}**

Nhấn ✅ để xác nhận và bắt đầu!
Nhấn ❌ để rời phòng chờ.
**━━━━━━━━━━━━━━━━━━━**"""
            await msg.edit(content=waiting_msg)
        except:
            pass

    async def update_game_countdown(self, message: discord.Message, game_id: int, duration: int):
        """Update the same message with countdown timer (plain text)."""
        start_time = time.time()
        end_time = start_time + duration

        try:
            while time.time() < end_time:
                remaining = int(end_time - time.time())
                minutes = remaining // 60
                seconds = remaining % 60

                # Get current game state
                game = await db_manager.execute_query(
                    "SELECT current_turn FROM active_games WHERE channel_id = ? AND is_active = 1",
                    (game_id,),
                    fetchone=True
                )
                if not game:
                    break

                # Get players info
                players = await db_manager.execute_query(
                    "SELECT user_id, background_name, hp, sanity FROM players WHERE game_id = ?",
                    (game_id,),
                    fetchall=True
                )

                players_info = "\n".join([
                    f"👤 {p['background_name']} | HP: {p['hp']} | Sanity: {p['sanity']}"
                    for p in players
                ])

                content = f"""**━━━━━━━━━━━━━━━━━━━**
**LƯỢT {game['current_turn']}**

Tình hình đang phát triển...

**📊 CÁC NGƯỜI CHƠI:**
{players_info}

**⏱️ Thời gian còn lại: {minutes}:{seconds:02d}**
**━━━━━━━━━━━━━━━━━━━**"""

                try:
                    await message.edit(content=content)
                except:
                    break

                await asyncio.sleep(2)  # Update every 2 seconds

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Countdown error: {e}")

    async def publish_turn_results(self, game_id: int, summary: str, turn_events: list):
        """Publish turn results in plain text."""
        game = await db_manager.execute_query(
            "SELECT private_channel_id FROM active_games WHERE channel_id = ?",
            (game_id,),
            fetchone=True
        )
        if not game or not game['private_channel_id']:
            return

        channel = self.bot.get_channel(game['private_channel_id'])
        if not channel:
            return

        # Format results as plain text
        events_text = "\n".join([f"• {event}" for event in turn_events])
        result_text = f"""**━━━━━━━━━━━━━━━━━━━**
**📜 KẾT QUẢ LƯỢT**

{summary}

**Sự kiện:**
{events_text}

**Đang chuyển sang lượt tiếp theo...**
**━━━━━━━━━━━━━━━━━━━**"""

        await channel.send(result_text)

        # Update main game message with countdown for next turn
        manager = game_engine.game_manager.get_manager(game_id)
        await manager.start_thinking_phase(duration=THINKING_PHASE_SECONDS)

    async def add_player_to_game(self, user_id, game_id, start_location_id):
        """Helper to add player (for host)."""
        background = {
            "id": "athlete",
            "name": "Vận Động Viên",
            "stats": {"hp": 110, "sanity": 100, "agi": 70, "acc": 50}
        }
        await db_manager.execute_query(
            """INSERT INTO players
               (user_id, game_id, background_id, background_name, hp, sanity, agi, acc, current_location_id, waiting_room_confirmed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (user_id, game_id, background['id'], background['name'],
             background['stats']['hp'], background['stats']['sanity'],
             background['stats']['agi'], background['stats']['acc'],
             start_location_id),
            commit=True
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle emoji reactions for game actions."""
        if payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        # Find game by message
        game = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE dashboard_message_id = ? AND is_active = 1",
            (payload.message_id,),
            fetchone=True
        )

        if not game:
            return

        game_id = game['channel_id']
        user_id = payload.user_id
        emoji_str = str(payload.emoji)

        # Map emoji to action
        action_map = {v: k for k, v in ACTION_EMOJIS.items()}
        action = action_map.get(emoji_str)

        if not action:
            return

        # Check if player is in game
        player = await db_manager.execute_query(
            "SELECT 1 FROM players WHERE user_id = ? AND game_id = ?",
            (user_id, game_id),
            fetchone=True
        )
        if not player:
            return

        # Process action
        if action == "confirm":
            result = await game_engine.confirm_player_action(user_id, game_id)
            if result:
                user = guild.get_member(user_id)
                if user:
                    try:
                        await message.reply(
                            f"🎉 {user.mention} **xác nhận hành động!**",
                            delete_after=5
                        )
                    except:
                        pass
        elif action == "skip":
            user = guild.get_member(user_id)
            if user:
                try:
                    await message.reply(
                        f"⏭️ {user.mention} **bỏ qua lượt này.**",
                        delete_after=5
                    )
                except:
                    pass
        else:
            # Register action
            await game_engine.register_action(user_id, game_id, action)
            action_names = {"attack": "Tấn Công", "flee": "Chạy Trốn", "search": "Tìm Kiếm"}
            user = guild.get_member(user_id)
            if user:
                try:
                    await message.reply(
                        f"✅ {user.mention} chọn **{action_names.get(action, action)}**!",
                        delete_after=5
                    )
                except:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(GameCommands(bot))

