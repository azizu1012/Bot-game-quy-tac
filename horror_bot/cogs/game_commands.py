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
import uuid

class JoinGameView(discord.ui.View):
    """Menu for joining a game - shows only Join button and counter."""
    def __init__(self, game_id: int, game_code: str, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.game_id = game_id
        self.game_code = game_code

    @discord.ui.button(label="📍 Vào Phòng Chờ", style=discord.ButtonStyle.success, emoji="📍")
    async def join_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_id = interaction.user.id
        
        # Check if already in game
        if await db_manager.check_player_in_game(user_id, self.game_id):
            await interaction.followup.send("⚠️ Bạn đã tham gia rồi!", ephemeral=True)
            return

        # Check if already in another game
        current_game = await db_manager.get_player_current_game(user_id)
        if current_game:
            await interaction.followup.send(
                "⚠️ Bạn đang tham gia một trò chơi khác!",
                ephemeral=True
            )
            return

        # Get game and map info
        game = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1",
            (self.game_id,),
            fetchone=True
        )
        if not game:
            await interaction.followup.send("❌ Phòng này không tồn tại.", ephemeral=True)
            return

        game_map_data = await db_manager.execute_query(
            "SELECT map_data FROM game_maps WHERE game_id = ?",
            (self.game_id,),
            fetchone=True
        )
        if not game_map_data:
            await interaction.followup.send("❌ Lỗi dữ liệu.", ephemeral=True)
            return

        map_nodes = json.loads(game_map_data['map_data'])
        start_node_id = list(map_nodes.get('nodes', {}).keys())[0] if map_nodes.get('nodes') else None

        # Create player profile
        profile = await background_service.create_player_profile(game['scenario_type'])

        # Add to database
        await db_manager.execute_query(
            """INSERT INTO players 
               (user_id, game_id, background_id, background_name, background_description,
                hp, sanity, agi, acc, current_location_id, waiting_room_confirmed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (user_id, self.game_id, profile['background_id'], profile['background_name'],
             profile['background_description'], profile['hp'], profile['sanity'],
             profile['agi'], profile['acc'], start_node_id),
            commit=True
        )

        # Grant private channel access
        private_channel = interaction.client.get_channel(game['private_channel_id'])
        if private_channel:
            await private_channel.set_permissions(
                interaction.user,
                read_messages=True,
                send_messages=False
            )

        # Update waiting room embed
        await update_join_menu_embed(interaction.client, self.game_id, self.game_code)

        await interaction.followup.send(
            f"✅ {interaction.user.mention} vào phòng chờ!\n"
            f"Background: **{profile['background_name']}**",
            ephemeral=False,
            delete_after=5
        )


class WaitingRoomView(discord.ui.View):
    """Waiting room confirmation - players confirm to start game."""
    def __init__(self, game_id: int, timeout: float = None):
        super().__init__(timeout=timeout)
        self.game_id = game_id

    @discord.ui.button(label="✅ Sẵn Sàng", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_ready(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_id = interaction.user.id

        # Mark as confirmed
        await db_manager.execute_query(
            "UPDATE players SET waiting_room_confirmed = 1 WHERE user_id = ? AND game_id = ?",
            (user_id, self.game_id),
            commit=True
        )

        await interaction.followup.send(
            f"✅ {interaction.user.mention} sẵn sàng!",
            ephemeral=False,
            delete_after=3
        )

        # Update waiting room
        await update_waiting_room_embed(interaction.client, self.game_id)

        # Check if all confirmed
        game = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE channel_id = ?",
            (self.game_id,),
            fetchone=True
        )
        if not game:
            return

        confirmations = await db_manager.get_waiting_room_confirmations(self.game_id)
        if confirmations['confirmed'] > 0 and confirmations['confirmed'] == confirmations['total']:
            # All players confirmed - start the game!
            await start_game_from_waiting_room(interaction.client, self.game_id)

    @discord.ui.button(label="❌ Hủy Bỏ", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject_ready(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_id = interaction.user.id
        game_id = self.game_id

        # Remove player from game
        await db_manager.execute_query(
            "DELETE FROM players WHERE user_id = ? AND game_id = ?",
            (user_id, game_id),
            commit=True
        )

        # Revoke channel access
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
            f"❌ {interaction.user.mention} đã rời phòng chờ.",
            ephemeral=False,
            delete_after=3
        )


async def update_join_menu_embed(bot: commands.Bot, game_id: int, game_code: str):
    """Update the join menu embed with current player count."""
    game = await db_manager.execute_query(
        "SELECT * FROM active_games WHERE channel_id = ?",
        (game_id,),
        fetchone=True
    )
    if not game or not game['private_channel_id']:
        return

    confirmations = await db_manager.get_waiting_room_confirmations(game_id)
    total = confirmations['total']

    private_channel = bot.get_channel(game['private_channel_id'])
    if not private_channel:
        return

    embed = discord.Embed(
        title="🎮 Phòng Chơi Đang Chờ",
        description=f"**Mã Phòng:** `{game_code}`",
        color=discord.Color.dark_red()
    )
    embed.add_field(
        name="👥 Người Chơi",
        value=f"0/{total}",
        inline=False
    )
    embed.add_field(
        name="📌 Hướng Dẫn",
        value="Nhấn nút **📍 Vào Phòng Chờ** để tham gia",
        inline=False
    )

    try:
        if game.get('join_menu_message_id'):
            msg = await private_channel.fetch_message(game['join_menu_message_id'])
            await msg.edit(embed=embed)
        else:
            view = JoinGameView(game_id, game_code)
            msg = await private_channel.send(embed=embed, view=view)
            await db_manager.execute_query(
                "UPDATE active_games SET join_menu_message_id = ? WHERE channel_id = ?",
                (msg.id, game_id),
                commit=True
            )
    except:
        pass


async def update_waiting_room_embed(bot: commands.Bot, game_id: int):
    """Update waiting room embed with confirmation status."""
    game = await db_manager.execute_query(
        "SELECT * FROM active_games WHERE channel_id = ?",
        (game_id,),
        fetchone=True
    )
    if not game or not game['private_channel_id']:
        return

    confirmations = await db_manager.get_waiting_room_confirmations(game_id)
    confirmed = confirmations['confirmed']
    total = confirmations['total']

    private_channel = bot.get_channel(game['private_channel_id'])
    if not private_channel:
        return

    embed = discord.Embed(
        title="🎮 Phòng Chờ - Xác Nhận Tham Gia",
        description="Tất cả người chơi vui lòng xác nhận để bắt đầu!",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="👥 Sẵn Sàng",
        value=f"{confirmed}/{total}",
        inline=False
    )
    embed.add_field(
        name="📌 Hướng Dẫn",
        value="✅ Nhấn để xác nhận\n❌ Nhấn để rời phòng",
        inline=False
    )

    # Progress bar
    progress = int((confirmed / total) * 10) if total > 0 else 0
    progress_bar = "🟩" * progress + "⬜" * (10 - progress)
    embed.add_field(
        name="⏳ Tiến Độ",
        value=progress_bar,
        inline=False
    )

    try:
        if game.get('waiting_room_message_id'):
            msg = await private_channel.fetch_message(game['waiting_room_message_id'])
            view = WaitingRoomView(game_id)
            await msg.edit(embed=embed, view=view)
        else:
            view = WaitingRoomView(game_id)
            msg = await private_channel.send(embed=embed, view=view)
            await db_manager.execute_query(
                "UPDATE active_games SET waiting_room_message_id = ? WHERE channel_id = ?",
                (msg.id, game_id),
                commit=True
            )
    except:
        pass


async def start_game_from_waiting_room(bot: commands.Bot, game_id: int):
    """Start game when all players confirm."""
    game = await db_manager.execute_query(
        "SELECT * FROM active_games WHERE channel_id = ?",
        (game_id,),
        fetchone=True
    )
    if not game or not game['private_channel_id']:
        return

    private_channel = bot.get_channel(game['private_channel_id'])
    if not private_channel:
        return

    # Clear chat
    try:
        async for message in private_channel.history(limit=100):
            try:
                await message.delete()
            except:
                pass
    except:
        pass

    # Generate world lore
    lore = await llm_service.generate_world_lore(game['scenario_type'])

    # Send lore (with chunking for 2000 char limit)
    chunks = chunk_text(lore, 1900)
    for chunk in chunks:
        await private_channel.send(chunk)

    # Get players and create initial scene
    players = await db_manager.execute_query(
        "SELECT user_id, background_name, hp, sanity FROM players WHERE game_id = ?",
        (game_id,),
        fetchall=True
    )

    players_info = "\n".join([
        f"👤 {p['background_name']} | HP: {p['hp']} | Sanity: {p['sanity']}"
        for p in players
    ])

    intro_description = await scenario_generator.generate_turn_intro(game['scenario_type'], 1, 1)

    scene_text = f"""**━━━━━━━━━━━━━━━━━━━**
**LƯỢT 1**

{intro_description}

**📊 CÁC NGƯỜI CHƠI:**
{players_info}

**⏱️ Đang đếm ngược...**
**━━━━━━━━━━━━━━━━━━━**"""

    game_msg = await private_channel.send(scene_text)

    # Update database
    await db_manager.execute_query(
        "UPDATE active_games SET dashboard_message_id = ?, waiting_room_stage = 2 WHERE channel_id = ?",
        (game_msg.id, game_id),
        commit=True
    )

    # Start game manager
    turn_manager = game_engine.game_manager.get_manager(game_id, publish_callback=publish_turn_results)
    await turn_manager.start_turn()

    # Start countdown
    asyncio.create_task(update_game_countdown(game_msg, game_id, TURN_TIME_SECONDS))


def chunk_text(text: str, max_length: int = 1900) -> list[str]:
    """Split text into chunks for Discord's 2000 char limit."""
    chunks = []
    current_chunk = ""

    for line in text.split('\n'):
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
        else:
            if current_chunk:
                current_chunk += '\n' + line
            else:
                current_chunk = line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks if chunks else [text]


async def update_game_countdown(message: discord.Message, game_id: int, duration: int):
    """Update countdown timer in place."""
    start_time = time.time()
    end_time = start_time + duration

    try:
        while time.time() < end_time:
            remaining = int(end_time - time.time())
            minutes = remaining // 60
            seconds = remaining % 60

            game = await db_manager.execute_query(
                "SELECT current_turn FROM active_games WHERE channel_id = ? AND is_active = 1",
                (game_id,),
                fetchone=True
            )
            if not game:
                break

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

            await asyncio.sleep(2)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Countdown error: {e}")


async def publish_turn_results(game_id: int, summary: str, turn_events: list):
    """Publish turn results in plain text."""
    game = await db_manager.execute_query(
        "SELECT private_channel_id FROM active_games WHERE channel_id = ?",
        (game_id,),
        fetchone=True
    )
    if not game or not game['private_channel_id']:
        return

    # This is handled by the cog listener
    return


class GameCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="newgame",
        description="🎮 Tạo một phòng chơi mới"
    )
    @app_commands.describe(scenario="📍 Chọn kịch bản (để trống = random)")
    async def new_game(self, interaction: discord.Interaction, scenario: str = None):
        await interaction.response.defer()

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

        # Random scenario
        if scenario is None:
            scenarios = ["asylum", "factory", "ghost_village", "cursed_mansion", "mine", "prison", "abyss", "dead_forest", "research_hospital", "ghost_ship"]
            scenario_value = random.choice(scenarios)
        else:
            scenario_value = scenario

        game_id = interaction.channel_id

        # Check if game already exists
        if await db_manager.execute_query(
            "SELECT 1 FROM active_games WHERE channel_id = ? AND is_active = 1",
            (game_id,),
            fetchone=True
        ):
            await interaction.followup.send("⚠️ Đã có phòng chơi trong kênh này.", ephemeral=True)
            return

        # Clean old data
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
                name=f"phong-choi-{random.randint(1, 999)}",
                category=None,
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=False)
                },
                reason="Tạo kênh riên cho trò chơi"
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
                current_turn, waiting_room_stage, game_code) 
               VALUES (?, ?, ?, ?, ?, 1, 1, 0, ?)""",
            (game_id, private_channel.id, interaction.user.id, interaction.user.id, scenario_value, game_code),
            commit=True
        )
        await db_manager.execute_query(
            "INSERT INTO game_maps (game_id, map_data) VALUES (?, ?)",
            (game_id, json.dumps(game_map.to_dict())),
            commit=True
        )

        # Add host as first player
        await self.add_player_to_game(interaction.user.id, game_id, game_map.start_node_id)

        # Notify in main channel
        await interaction.followup.send(
            f"🎮 **Phòng Mới!** {private_channel.mention}\n"
            f"Kịch Bản: `{scenario_value}`\n"
            f"Mã Phòng: `{game_code}`"
        )

        # Create join menu in private channel
        await update_join_menu_embed(self.bot, game_id, game_code)

    @app_commands.command(
        name="join",
        description="👻 Tham gia phòng chơi bằng mã"
    )
    @app_commands.describe(code="🔑 Mã phòng (Room Code)")
    async def join_by_code(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer()

        # Find game by code - need to search all games
        all_games = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE is_active = 1",
            (),
            fetchall=True
        )

        target_game = None
        if all_games:
            for g in all_games:
                if g.get('game_code') == code:
                    target_game = g
                    break
        
        if not target_game:
            await interaction.followup.send("❌ Mã phòng không tồn tại.", ephemeral=True)
            return

        game_id = target_game['channel_id']
        user_id = interaction.user.id

        # Check if already in game
        if await db_manager.check_player_in_game(user_id, game_id):
            await interaction.followup.send("⚠️ Bạn đã tham gia phòng này!", ephemeral=True)
            return

        # Check if already in another game
        current_game = await db_manager.get_player_current_game(user_id)
        if current_game:
            await interaction.followup.send("⚠️ Bạn đang tham gia một phòng khác!", ephemeral=True)
            return

        # Get map
        game_map_data = await db_manager.execute_query(
            "SELECT map_data FROM game_maps WHERE game_id = ?",
            (game_id,),
            fetchone=True
        )
        if not game_map_data:
            await interaction.followup.send("❌ Lỗi dữ liệu.", ephemeral=True)
            return

        map_nodes = json.loads(game_map_data['map_data'])
        start_node_id = list(map_nodes.get('nodes', {}).keys())[0] if map_nodes.get('nodes') else None

        # Create profile
        profile = await background_service.create_player_profile(target_game['scenario_type'])

        # Add player
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

        # Grant access
        private_channel = self.bot.get_channel(target_game['private_channel_id'])
        if private_channel:
            await private_channel.set_permissions(
                interaction.user,
                read_messages=True,
                send_messages=False
            )
            await update_join_menu_embed(self.bot, game_id, code)

        await interaction.followup.send(
            f"✅ Đã vào phòng `{code}`!\nBackground: **{profile['background_name']}**",
            ephemeral=False,
            delete_after=5
        )

    @app_commands.command(
        name="readyup",
        description="✅ Xác nhận sẵn sàng chơi (từ phòng chờ)"
    )
    async def ready_up(self, interaction: discord.Interaction):
        await interaction.response.defer()

        game_id = interaction.channel_id
        user_id = interaction.user.id

        game = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE channel_id = ?",
            (game_id,),
            fetchone=True
        )

        if not game:
            await interaction.followup.send("❌ Không có phòng nào.", ephemeral=True)
            return

        if game['waiting_room_stage'] != 1:
            await interaction.followup.send(
                "❌ Không ở trong phòng chờ!",
                ephemeral=True
            )
            return

        # Mark as confirmed
        await db_manager.execute_query(
            "UPDATE players SET waiting_room_confirmed = 1 WHERE user_id = ? AND game_id = ?",
            (user_id, game_id),
            commit=True
        )

        await interaction.followup.send(
            f"✅ {interaction.user.mention} sẵn sàng!",
            ephemeral=False,
            delete_after=3
        )

        # Update waiting room
        await update_waiting_room_embed(self.bot, game_id)

        # Check if all confirmed
        confirmations = await db_manager.get_waiting_room_confirmations(game_id)
        if confirmations['confirmed'] > 0 and confirmations['confirmed'] == confirmations['total']:
            await start_game_from_waiting_room(self.bot, game_id)

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

        creator_id = await db_manager.get_game_creator(game_id)
        
        if user_id == creator_id:
            await self.cleanup_game(game_id)
            await interaction.followup.send("✅ Trò chơi đã kết thúc.", ephemeral=False)
        else:
            await interaction.followup.send(
                "❌ Chỉ người tạo game mới có thể kết thúc!",
                ephemeral=True
            )

    async def cleanup_game(self, game_id: int):
        """Clean up game."""
        game = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1",
            (game_id,),
            fetchone=True
        )
        if not game:
            return

        game_engine.game_manager.end_game(game_id)

        await db_manager.execute_query(
            "UPDATE active_games SET is_active = 0 WHERE channel_id = ?",
            (game_id,),
            commit=True
        )

        if game['private_channel_id']:
            try:
                channel = self.bot.get_channel(game['private_channel_id'])
                if channel:
                    await channel.delete(reason="Game ended")
            except:
                pass

    async def add_player_to_game(self, user_id, game_id, start_location_id):
        """Add host as first player."""
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

        # Find game by dashboard message
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

        # Check if player in game
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
                            f"🎉 {user.mention} **xác nhận!**",
                            delete_after=5
                        )
                    except:
                        pass
        else:
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
