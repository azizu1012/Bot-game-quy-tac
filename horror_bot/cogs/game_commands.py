# -*- coding: utf-8 -*-
"""
HORROR BOT - GAME COMMANDS (Free-Form Text Actions)
3-tier channel architecture: Lobby + Dashboard + Private Per-User
"""

import discord
from discord import app_commands
from discord.ext import commands
from database import db_manager
from services import game_engine, map_generator, scenario_generator, llm_service, background_service, leaderboard_service
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

        # Get game ID - use a hash of game_code and user to create a unique integer
        import hashlib
        game_id = int(hashlib.md5(f"{game_code}{interaction.user.id}".encode()).hexdigest()[:16], 16) % (2**63)
        print(f"   └─ Game ID: {game_id}")

        # Load scenario map
        print(f"   └─ Loading scenario map...")
        scenario_file = f"data/scenarios/{scenario_value}.json"
        game_map = map_generator.generate_map_structure(scenario_file)
        if not game_map:
            await interaction.followup.send("❌ Lỗi: Không thể tạo bản đồ.", ephemeral=True)
            return

        # Create channel structure: Lobby + Dashboard (as thread inside lobby)
        print(f"   └─ Creating lobby channel...")
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

            # TIER 2: Dashboard thread inside lobby
            dashboard_thread = await lobby_channel.create_thread(
                name=f"📊-dashboard-{scenario_value}",
                auto_archive_duration=60
            )
            print(f"      ✅ Dashboard thread created: #{dashboard_thread.name}")
            dashboard_channel_id = dashboard_thread.id

        except discord.Forbidden:
            await interaction.followup.send("❌ Bot không có quyền tạo kênh.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi tạo kênh: {e}", ephemeral=True)
            return

        # Save to database
        print(f"   └─ Saving to database...")
        try:
            print(f"      └─ Inserting into active_games...")
            await db_manager.execute_query(
                """INSERT INTO active_games 
                   (channel_id, lobby_channel_id, dashboard_channel_id, host_id, 
                    game_creator_id, scenario_type, game_code, setup_by_admin_id, is_active) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (game_id, lobby_channel.id, dashboard_channel_id, interaction.user.id,
                 interaction.user.id, scenario_value, game_code, guild_setup['created_by']),
                commit=True
            )
            print(f"      ✅ active_games saved")

            # Save map
            print(f"      └─ Inserting into game_maps...")
            await db_manager.execute_query(
                "INSERT INTO game_maps (game_id, map_data) VALUES (?, ?)",
                (game_id, json.dumps(game_map.to_dict())),
                commit=True
            )
            print(f"      ✅ game_maps saved")

            # Initialize game context
            print(f"      └─ Inserting into game_context...")
            await db_manager.execute_query(
                """INSERT INTO game_context (game_id, scenario_type, current_threat_level) 
                   VALUES (?, ?, 0)""",
                (game_id, scenario_value),
                commit=True
            )
            print(f"      ✅ game_context saved")

            # Add creator as first player
            print(f"      └─ Adding player to game...")
            await self._add_player_to_game(interaction.user.id, game_id, game_map.start_node_id, scenario_value)
            print(f"      ✅ Player added")

        except Exception as e:
            print(f"❌ Database error: {e}")
            await interaction.followup.send(f"❌ Lỗi cơ sở dữ liệu: {e}", ephemeral=True)
            return

        # Send lore to lobby
        print(f"   └─ Generating scenario lore...")
        try:
            greeting = await llm_service.generate_simple_greeting(scenario_value)
            print(f"      └─ Greeting generated: {greeting[:50]}...")
        except Exception as e:
            print(f"⚠️ Greeting error: {e}")
            greeting = f"📍 Bạn đang ở {scenario_value}..."
        
        # Create main embed with greeting
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
        print(f"      ✅ Lore embed sent to lobby")
        
        # Generate and save game rules
        print(f"   └─ Generating game rules...")
        try:
            rules_dict = await llm_service.generate_dark_rules(scenario_value)
            await db_manager.save_game_rules(game_id, rules_dict)
            
            public_rules = rules_dict.get("public_rules", [])
            if public_rules:
                rules_text = "**📜 CÁC QUY TẮC SINH TỒN:**\n"
                for i, rule in enumerate(public_rules, 1):
                    rules_text += f"**{i}.** {rule.get('rule', '...')}\n"
                rules_text += "\n*Hãy cẩn thận, không phải quy tắc nào cũng là lời khuyên tốt...*"
                await lobby_channel.send(rules_text)
                print(f"      ✅ Sent {len(public_rules)} public rules to lobby.")
            else:
                 await lobby_channel.send("**CẢNH BÁO:** Không có quy tắc nào được đặt ra. Hãy tự mình khám phá.")
                 print(f"      ⚠️ No public rules were generated.")

        except Exception as e:
            print(f"      ⚠️ Error generating or sending rules: {e}")
            await lobby_channel.send("**CẢNH BÁO:** Có lỗi khi tạo ra các quy tắc của thế giới này. Mọi thứ đều khó lường.")
        
        # Generate detailed world lore in background (non-blocking)
        asyncio.create_task(self._send_world_lore_async(lobby_channel, scenario_value))

        # Notify in main channel
        await interaction.followup.send(
            f"🎮 **Phòng Mới!** {lobby_channel.mention}\n"
            f"📊 Dashboard: {dashboard_thread.mention}\n"
            f"Kịch Bản: `{scenario_value}`\n"
            f"Mã Phòng: `{game_code}`"
        )
        print(f"✅ [NEW_GAME] Complete!\n")

    async def _add_player_to_game(self, user_id: int, game_id: str, start_location_id: str, scenario_type: str):
        """Add player to game with default profile."""
        try:
            print(f"        └─ Creating player profile...")
            profile = await background_service.create_player_profile(scenario_type)
            print(f"        └─ Inserting player into database...")
            
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
            print(f"        ✅ Player {user_id} added to game {game_id}")
        except Exception as e:
            print(f"        ❌ Error adding player: {e}")

    async def _send_world_lore_async(self, lobby_channel: discord.TextChannel, scenario_type: str):
        """Generate and send detailed world lore in background (non-blocking)."""
        try:
            print(f"      └─ Generating detailed world lore in background...")
            world_lore = await llm_service.generate_world_lore(scenario_type)
            print(f"      └─ World lore generated: {len(world_lore)} characters")
            
            if world_lore and len(world_lore) > 0:
                # Split into chunks if too long (Discord message limit is 2000 chars)
                chunks = [world_lore[i:i+1900] for i in range(0, len(world_lore), 1900)]
                for i, chunk in enumerate(chunks):
                    try:
                        if i == 0:
                            await lobby_channel.send(f"**📜 Chi tiết Lore:**\n{chunk}")
                        else:
                            await lobby_channel.send(f"**Tiếp tục:**\n{chunk}")
                    except Exception as e:
                        print(f"        ⚠️ Error sending lore chunk {i}: {e}")
                print(f"      ✅ World lore sent ({len(chunks)} messages)")
        except Exception as e:
            print(f"      ⚠️ Error generating world lore: {e}")
            try:
                await lobby_channel.send(f"**📜 Lore:** *Đang tải chi tiết lore... (Lỗi: {str(e)[:50]})*")
            except:
                pass

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

    @app_commands.command(name="endgame", description="🏁 Kết thúc game (host tắt ngay, người khác vote 50%)")
    async def end_game(self, interaction: discord.Interaction):
        """End game - host can end immediately, others need 50% vote."""
        await interaction.response.defer()
        
        user_id = interaction.user.id
        
        # Check if command is used in a lobby channel
        if not interaction.channel.name.startswith("game-lobby-"):
            await interaction.followup.send(
                "❌ Lệnh này chỉ có thể dùng trong lobby của game!",
                ephemeral=True
            )
            return
        
        # Find game by lobby channel
        game = await db_manager.execute_query(
            "SELECT channel_id, game_code, host_id FROM active_games WHERE lobby_channel_id = ?",
            (interaction.channel.id,),
            fetchone=True
        )
        
        if not game:
            await interaction.followup.send("❌ Game không tồn tại!", ephemeral=True)
            return
        
        game_id = game['channel_id']
        is_host = user_id == game['host_id']
        
        print(f"\n🏁 [ENDGAME] User {user_id} initiated endgame in game {game['game_code']}")
        print(f"   └─ Is host: {is_host}")
        
        # Check if user is in game
        player = await db_manager.execute_query(
            "SELECT * FROM players WHERE user_id = ? AND game_id = ?",
            (user_id, game_id),
            fetchone=True
        )
        
        if not player:
            await interaction.followup.send("❌ Bạn không tham gia game này!", ephemeral=True)
            return
        
        # If host, end immediately
        if is_host:
            print(f"   └─ Host ending game immediately")
            await self._force_delete_game(game_id, game['game_code'], f"Host {interaction.user.name} ended")
            await interaction.followup.send(
                f"⛔ **Host {interaction.user.name} đã kết thúc game!**\nTất cả channels sẽ bị xóa...",
                ephemeral=False
            )
            return
        
        # For non-host players, create a vote
        print(f"   └─ Non-host player, starting vote")
        
        # Get all players in game
        all_players = await db_manager.execute_query(
            "SELECT user_id FROM players WHERE game_id = ?",
            (game_id,),
            fetchall=True
        )
        
        total_players = len(all_players)
        votes_needed = max(1, (total_players + 1) // 2)  # 50% + 1 for majority
        
        print(f"   └─ Total players: {total_players}, votes needed: {votes_needed}")
        
        # Create vote view
        class EndGameVote(discord.ui.View):
            def __init__(vote_self):
                super().__init__(timeout=300)  # 5 minutes vote
                vote_self.votes = {user_id}  # Initiator votes yes
                vote_self.voted_users = {user_id}
                vote_self.voted = False
            
            @discord.ui.button(label="✅ Đồng ý (0/X)", style=discord.ButtonStyle.green)
            async def agree_button(vote_self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                if btn_interaction.user.id in vote_self.voted_users:
                    await btn_interaction.response.send_message("Bạn đã vote rồi!", ephemeral=True)
                    return
                
                vote_self.votes.add(btn_interaction.user.id)
                vote_self.voted_users.add(btn_interaction.user.id)
                
                # Update button label
                button.label = f"✅ Đồng ý ({len(vote_self.votes)}/{votes_needed})"
                
                await btn_interaction.response.defer()
                
                # Check if vote passed
                if len(vote_self.votes) >= votes_needed:
                    vote_self.voted = True
                    for item in vote_self.children:
                        item.disabled = True
                    
                    await interaction.channel.send(
                        f"✅ **Vote thông qua!** Kết thúc game `{game['game_code']}`..."
                    )
                    await self._force_delete_game(game_id, game['game_code'], 
                                                 f"Voted ended by {interaction.user.name}")
                    print(f"✅ [ENDGAME] Game {game['game_code']} ended by vote\n")
                
                # Update the vote message
                await vote_msg.edit(view=vote_self)
            
            @discord.ui.button(label="❌ Từ chối", style=discord.ButtonStyle.red)
            async def refuse_button(vote_self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                if btn_interaction.user.id in vote_self.voted_users:
                    await btn_interaction.response.send_message("Bạn đã vote rồi!", ephemeral=True)
                    return
                
                vote_self.voted_users.add(btn_interaction.user.id)
                
                await btn_interaction.response.defer()
                
                # Check if refuse votes enough to block
                refuse_votes = total_players - len(vote_self.votes)
                if refuse_votes >= votes_needed:
                    vote_self.voted = False
                    for item in vote_self.children:
                        item.disabled = True
                    
                    await interaction.channel.send(
                        f"❌ **Vote bị từ chối!** Game tiếp tục..."
                    )
                    print(f"❌ [ENDGAME] Vote rejected for game {game['game_code']}\n")
                
                # Update the vote message
                agree_button = vote_self.children[0]
                agree_button.label = f"✅ Đồng ý ({len(vote_self.votes)}/{votes_needed})"
                await vote_msg.edit(view=vote_self)
        
        vote = EndGameVote()
        agree_button = vote.children[0]
        agree_button.label = f"✅ Đồng ý (1/{votes_needed})"
        
        vote_msg = await interaction.followup.send(
            f"🗳️ **{interaction.user.name} muốn kết thúc game!**\n"
            f"Cần {votes_needed}/{total_players} phiếu đồng ý\n"
            f"*Vote sẽ đóng trong 5 phút*",
            view=vote,
            ephemeral=False
        )
    
    async def _force_delete_game(self, game_id: str, game_code: str, reason: str):
        """Delete game and all related channels."""
        try:
            print(f"   └─ Deleting game {game_code}: {reason}")
            
            # Get game info
            game = await db_manager.execute_query(
                "SELECT lobby_channel_id, dashboard_channel_id FROM active_games WHERE channel_id = ?",
                (game_id,),
                fetchone=True
            )
            
            if game:
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
                                await channel.delete(reason=reason)
                        except Exception as e:
                            print(f"      ⚠️ Error deleting private channel: {e}")
                
                # Delete lobby and dashboard
                for channel_id in [game['lobby_channel_id'], game['dashboard_channel_id']]:
                    if channel_id:
                        try:
                            channel = self.bot.get_channel(int(channel_id))
                            if channel:
                                await channel.delete(reason=reason)
                        except Exception as e:
                            print(f"      ⚠️ Error deleting channel: {e}")
            
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
            
            print(f"      ✅ Game deleted: {game_code}\n")
            
        except Exception as e:
            print(f"❌ Error in _force_delete_game: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(GameCommands(bot))
