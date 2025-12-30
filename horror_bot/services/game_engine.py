# -*- coding: utf-8 -*-
"""
HORROR BOT - GAME ENGINE (Free-Form Action Processing)
Per-user action pipeline with automatic encounter detection and real-time dashboard updates
"""

import asyncio
import json
import discord
from database import db_manager
from services import llm_service, leaderboard_service


def create_progress_bar(current: int, max_val: int, width: int = 10) -> str:
    """Create text-based progress bar [████░░░░░]"""
    if max_val == 0:
        return "░" * width
    filled = int((current / max_val) * width)
    return "█" * filled + "░" * (width - filled)


async def process_free_text_action(
    player_id: int,
    game_id: str,
    action_text: str,
    channel: discord.TextChannel,
    bot: discord.Client
) -> None:
    """
    Main 6-step pipeline for free-form player action processing.
    
    Steps:
    1. Gather player context (location, inventory, stats, history)
    2. Call LLM with per-player DM system prompt
    3. Parse LLM JSON response, update DB atomically
    4. Check for encounters (get_players_at_location)
    5. Update real-time dashboard
    6. Send response to player's private channel
    """
    try:
        # ======================================================================
        # STEP 1: GATHER CONTEXT
        # ======================================================================
        player = await db_manager.execute_query(
            """SELECT user_id, hp, sanity, agi, acc, background_name,
               current_location_id, location_name, inventory,
               llm_conversation_history, private_channel_id
               FROM players WHERE user_id = ? AND game_id = ?""",
            (player_id, game_id),
            fetchone=True
        )
        
        if not player:
            return
        
        location_name = player['location_name'] or "An Unknown Place"
        inventory = json.loads(player['inventory'] or '[]')
        conversation_history = json.loads(player['llm_conversation_history'] or '[]')
        
        # ======================================================================
        # STEP 2: CALL LLM WITH PER-PLAYER DM PROMPT
        # ======================================================================
        system_prompt = f"""You are a horror game Dungeon Master.

Current Location: {location_name}
Player Stats: HP {player['hp']}/100, Sanity {player['sanity']}/100, AGI {player['agi']}, ACC {player['acc']}
Inventory: {', '.join(inventory) if inventory else 'Empty'}

Respond to the player's action with a JSON object:
{{
    "success": bool,
    "description": "What happened (1-2 sentences)",
    "hp_change": int (negative for damage),
    "sanity_change": int (negative for fear),
    "new_location_id": "same or new room ID",
    "discovered_items": ["item1", "item2"]
}}

Be concise. Horror tone. Vietnamese.
"""
        
        llm_response = await llm_service.process_player_action(
            action_text=action_text,
            system_prompt=system_prompt,
            conversation_history=conversation_history
        )
        
        # ======================================================================
        # STEP 3: PARSE LLM RESPONSE
        # ======================================================================
        try:
            action_result = json.loads(llm_response)
        except json.JSONDecodeError:
            action_result = {
                "success": False,
                "description": "Hệ thống AI gặp lỗi phân tích.",
                "hp_change": 0,
                "sanity_change": 0,
                "new_location_id": "same",
                "discovered_items": []
            }
        
        # ======================================================================
        # STEP 3.5: CHECK FOR HIDDEN RULE VIOLATIONS
        # ======================================================================
        violation_penalty = 0
        violation_reason = None
        hidden_rules = await db_manager.get_game_rules(game_id, is_public=False)
        if hidden_rules:
            violation_check = await llm_service.check_rule_violation(
                hidden_rules=hidden_rules,
                action_text=action_text,
                action_description=action_result.get('description', '')
            )
            if violation_check.get('violated'):
                print(f"🚨 Player {player_id} violated rule: {violation_check.get('rule_violated')}")
                violation_penalty = -15  # Penalty for breaking a hidden rule
                violation_reason = violation_check.get('reason', 'Bạn cảm thấy một sự ớn lạnh chạy dọc sống lưng...')

        # ======================================================================
        # STEP 4: UPDATE DB ATOMICALLY
        # ======================================================================
        # Combine penalties from action and violation
        total_hp_change = action_result.get('hp_change', 0)
        total_sanity_change = action_result.get('sanity_change', 0) + violation_penalty
        
        new_hp = max(0, min(100, player['hp'] + total_hp_change))
        new_sanity = max(0, min(100, player['sanity'] + total_sanity_change))
        
        await db_manager.execute_query(
            """UPDATE players SET hp = ?, sanity = ?, last_action_result = ?
               WHERE user_id = ? AND game_id = ?""",
            (
                new_hp,
                new_sanity,
                json.dumps(action_result),
                player_id,
                game_id
            ),
            commit=True
        )
        
        # Append to conversation history (rolling 10-message window)
        await db_manager.append_to_llm_history(
            user_id=player_id,
            game_id=game_id,
            role="user",
            content=action_text
        )
        await db_manager.append_to_llm_history(
            user_id=player_id,
            game_id=game_id,
            role="assistant",
            content=action_result['description']
        )
        
        # ======================================================================
        # STEP 5: HANDLE LOCATION CHANGES AND ENCOUNTERS
        # ======================================================================
        new_location_id = action_result.get('new_location_id', 'same')
        if new_location_id != 'same':
            await db_manager.execute_query(
                """UPDATE players SET current_location_id = ? WHERE user_id = ? AND game_id = ?""",
                (new_location_id, player_id, game_id),
                commit=True
            )
        else:
            new_location_id = player['current_location_id']
        
        # Check for other players at same location
        other_players = await db_manager.get_players_at_location(game_id, new_location_id)
        other_players = [p for p in other_players if p['user_id'] != player_id and p['hp'] > 0]
        
        encounter_text = None
        if other_players:
            other_player_names = [p['background_name'] for p in other_players]
            scenario_type = (await db_manager.execute_query(
                "SELECT scenario_type FROM active_games WHERE channel_id = ?",
                (game_id,), fetchone=True
            ))['scenario_type']

            encounter_text = await llm_service.generate_encounter(
                action_description=action_text,
                player_name=player['background_name'],
                other_players=other_player_names,
                scenario_type=scenario_type
            )
            
            # Record encounter
            await db_manager.record_encounter(
                game_id=game_id,
                location_id=new_location_id,
                player_ids=[player_id] + [p['user_id'] for p in other_players],
                encounter_text=encounter_text
            )
        
        # ======================================================================
        # STEP 6: UPDATE REAL-TIME DASHBOARD
        # ======================================================================
        await update_game_dashboard(game_id, bot)
        
        # ======================================================================
        # STEP 7: SEND RESPONSE TO PLAYER'S PRIVATE CHANNEL
        # ======================================================================
        private_channel_id = player['private_channel_id']
        if private_channel_id:
            private_channel = bot.get_channel(int(private_channel_id))
            if private_channel:
                # Build response embed
                embed = discord.Embed(
                    title="⚔️ Kết quả hành động",
                    description=action_result['description'],
                    color=discord.Color.dark_red()
                )
                
                embed.add_field(
                    name="📊 Chỉ số",
                    value=f"HP: **{new_hp}** ({total_hp_change:+d})\nSanity: **{new_sanity}** ({total_sanity_change:+d})",
                    inline=False
                )

                if violation_reason:
                    embed.add_field(
                        name="⚠️ Cảm giác bất an",
                        value=f"*{violation_reason}*",
                        inline=False
                    )
                
                if action_result.get('discovered_items'):
                    embed.add_field(
                        name="📦 Nhặt được",
                        value=", ".join(action_result['discovered_items']),
                        inline=False
                    )
                
                await private_channel.send(embed=embed)
                
                # Send encounter message if applicable
                if encounter_text:
                    encounter_embed = discord.Embed(
                        title="👥 Gặp gỡ!",
                        description=encounter_text,
                        color=discord.Color.gold()
                    )
                    await private_channel.send(embed=encounter_embed)
    
    except Exception as e:
        print(f"❌ Error processing action: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    # ======================================================================
    # STEP 8: CHECK FOR GAME COMPLETION (Auto-create leaderboard)
    # ======================================================================
    try:
        game_guild = None
        game_info = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE channel_id = ?",
            (game_id,),
            fetchone=True
        )
        
        if game_info:
            # Get guild from lobby channel
            try:
                lobby_ch = bot.get_channel(int(game_info['lobby_channel_id']))
                if lobby_ch:
                    game_guild = lobby_ch.guild
            except:
                pass
        
        if game_guild:
            completion = await leaderboard_service.check_game_completion(
                game_id, bot, game_guild
            )
            if completion:
                print(f"[AUTO] Leaderboard created for game {game_id}")
    except Exception as e:
        print(f"⚠️ Error checking game completion: {e}")


async def update_game_dashboard(game_id: str, bot: discord.Client) -> None:
    """
    Update real-time dashboard with all player stats.
    Edits existing message (not spam new messages).
    """
    try:
        game = await db_manager.get_game_by_id(game_id)
        if not game:
            return
        
        dashboard_channel = bot.get_channel(int(game['dashboard_channel_id']))
        if not dashboard_channel:
            return
        
        # Build player stats
        players = await db_manager.execute_query(
            """SELECT user_id, background_name, hp, sanity, location_name
               FROM players WHERE game_id = ? ORDER BY background_name""",
            (game_id,),
            fetchall=True
        )
        
        # Create embed
        embed = discord.Embed(
            title="📊 Game Dashboard",
            color=discord.Color.dark_gray()
        )
        
        for player in players:
            hp_bar = create_progress_bar(player['hp'], 100)
            sanity_bar = create_progress_bar(player['sanity'], 100)
            location = player['location_name'] or "Unknown"
            status = "🟢 Alive" if player['hp'] > 0 else "💀 Dead"
            
            player_info = (
                f"**HP:** {hp_bar} {player['hp']}/100\n"
                f"**Sanity:** {sanity_bar} {player['sanity']}/100\n"
                f"**Location:** {location}\n"
                f"**Status:** {status}"
            )
            
            embed.add_field(
                name=player['background_name'],
                value=player_info,
                inline=True
            )
        
        # Edit or create message
        dashboard_message_id = game['dashboard_message_id']
        if dashboard_message_id:
            try:
                message = await dashboard_channel.fetch_message(int(dashboard_message_id))
                await message.edit(embed=embed)
            except discord.NotFound:
                # Message deleted, create new one
                message = await dashboard_channel.send(embed=embed)
                await db_manager.execute_query(
                    "UPDATE active_games SET dashboard_message_id = ? WHERE game_id = ?",
                    (str(message.id), game_id),
                    commit=True
                )
        else:
            # Create new message
            message = await dashboard_channel.send(embed=embed)
            await db_manager.execute_query(
                "UPDATE active_games SET dashboard_message_id = ? WHERE game_id = ?",
                (str(message.id), game_id),
                commit=True
            )
    
    except Exception as e:
        print(f"❌ Error updating dashboard: {e}")
