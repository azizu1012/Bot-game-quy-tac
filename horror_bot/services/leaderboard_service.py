# -*- coding: utf-8 -*-
"""
HORROR BOT - LEADERBOARD SERVICE
AI-powered game rating and leaderboard generation
"""

from services import llm_service
from database import db_manager
import discord
import json
import re

# Rating scale: F (worst) to SS (best)
RATING_SCALE = ["F", "D", "C", "B", "A", "S", "SS"]

async def check_game_completion(game_id: str, bot: discord.Client, guild: discord.Guild) -> bool:
    """
    Check if game should end (all objectives completed or all players dead/gone).
    Returns True if game is completed and leaderboard was created.
    """
    try:
        # Get game info
        game = await db_manager.execute_query(
            "SELECT channel_id, game_code, scenario_type, lobby_channel_id FROM active_games WHERE channel_id = ?",
            (game_id,),
            fetchone=True
        )
        
        if not game:
            return False
        
        # Get all players
        players = await db_manager.execute_query(
            "SELECT user_id, hp FROM players WHERE game_id = ?",
            (game_id,),
            fetchall=True
        )
        
        if not players:
            return False
        
        # Check if all players are dead or HP <= 0
        alive_players = [p for p in players if p['hp'] > 0]
        
        if len(alive_players) == 0:
            # All players dead - game over, create leaderboard
            print(f"\n💀 [GAME_OVER] All players dead in game {game['game_code']}")
            await _create_leaderboard_and_cleanup(
                game_id, game['game_code'], game['scenario_type'], 
                game['lobby_channel_id'], bot, guild,
                "Tất cả người chơi đã bị tiêu diệt"
            )
            return True
        
        # Check if all players completed objectives
        # For now, we'll use a simple heuristic: if all players have reached sanctuary/exit
        # In a real game, you'd track actual objective completion
        
        return False
    
    except Exception as e:
        print(f"❌ Error checking game completion: {e}")
        return False

async def _create_leaderboard_and_cleanup(
    game_id: str,
    game_code: str,
    scenario_type: str,
    lobby_channel_id: int,
    bot: discord.Client,
    guild: discord.Guild,
    completion_reason: str
) -> None:
    """Create leaderboard, ping users, and cleanup game."""
    try:
        print(f"   └─ Evaluating game with AI...")
        
        # Evaluate game with AI
        evaluation = await evaluate_game_completion(game_id, scenario_type)
        
        if not evaluation:
            print(f"❌ Failed to evaluate game {game_code}")
            return
        
        # Get lobby channel and category
        lobby_channel = guild.get_channel(lobby_channel_id)
        category = lobby_channel.category if lobby_channel else None
        
        # Create leaderboard channel
        leaderboard_channel = await create_leaderboard_channel(
            guild, category, evaluation, game_code, completion_reason
        )
        
        # Delete private channels
        players = await db_manager.execute_query(
            "SELECT user_id, private_channel_id FROM players WHERE game_id = ?",
            (game_id,),
            fetchall=True
        )
        
        for player in players:
            if player['private_channel_id']:
                try:
                    channel = bot.get_channel(int(player['private_channel_id']))
                    if channel:
                        await channel.delete(reason=f"Game {game_code} completed")
                except Exception as e:
                    print(f"      ⚠️ Error deleting private channel: {e}")
        
        # Delete lobby
        if lobby_channel:
            try:
                # Give time to see leaderboard
                import asyncio
                await asyncio.sleep(10)
                await lobby_channel.delete(reason=f"Game {game_code} completed")
            except Exception as e:
                print(f"      ⚠️ Error deleting lobby: {e}")
        
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
        
        if leaderboard_channel:
            # Ping users with their ratings
            for player in evaluation.get('players', []):
                user_id = player['user_id']
                rating = player['rating']
                emoji = _get_rating_emoji(rating)
                try:
                    await leaderboard_channel.send(f"<@{user_id}> {emoji} **{rating}**")
                except Exception as e:
                    print(f"      ⚠️ Error pinging user: {e}")
        
        print(f"✅ [LEADERBOARD] Game {game_code} completed and leaderboard created\n")
        
    except Exception as e:
        print(f"❌ Error creating leaderboard: {e}")


async def evaluate_game_completion(game_id: str, scenario_type: str) -> dict:
    """
    Evaluate game completion and generate ratings for all players.
    Ratings based on:
    - HP & Sanity (visible metric)
    - Objectives completion (hidden)
    - Hidden criteria: encounters, items found, exploration (A→SS)
    
    Returns:
    {
        "game_code": "ABC123",
        "scenario": "prison",
        "completion_rating": "S",
        "players": [
            {
                "user_id": 123456,
                "name": "Player Name",
                "hp": 80,
                "sanity": 45,
                "rating": "A",
                "reason": "Sống sót với HP cao, sanity hợp lý"
            }
        ]
    }
    """
    try:
        # Get game info
        game = await db_manager.execute_query(
            "SELECT game_code, scenario_type FROM active_games WHERE channel_id = ?",
            (game_id,),
            fetchone=True
        )
        
        if not game:
            return None
        
        # Load scenario to get objectives
        scenario_file = f"data/scenarios/{scenario_type}.json"
        try:
            import json as json_lib
            with open(scenario_file, 'r', encoding='utf-8') as f:
                scenario_data = json_lib.load(f)
            objectives = scenario_data.get('objectives', [])
        except:
            objectives = []
        
        # Get all players
        players = await db_manager.execute_query(
            "SELECT user_id, hp, sanity, agi, acc, background_name, inventory FROM players WHERE game_id = ?",
            (game_id,),
            fetchall=True
        )
        
        if not players:
            return None
        
        # Evaluate each player with hidden criteria
        players_eval = []
        total_completion = 0
        
        for player in players:
            rating, hidden_score = _calculate_player_rating(
                player, objectives, game_id
            )
            
            # Only show visible metrics in reason (HP, Sanity)
            hp = player['hp']
            sanity = player['sanity']
            
            if hp <= 0:
                reason = "Bị tiêu diệt trong trận đánh"
            elif sanity <= 20:
                reason = "Bị sợ hãi, mất tinh thần"
            elif hp <= 30:
                reason = f"Sống sót nhưng bị thương nặng (HP: {hp}/100)"
            elif sanity <= 40:
                reason = f"Sống sót với tinh thần tổn thương (Sanity: {sanity}/100)"
            else:
                reason = f"Sống sót tốt (HP: {hp}/100, Sanity: {sanity}/100)"
            
            players_eval.append({
                "user_id": player['user_id'],
                "rating": rating,
                "reason": reason,
                "_hidden_score": hidden_score  # For internal use, not displayed
            })
            
            total_completion += hidden_score
        
        # Overall completion rating based on hidden metrics
        avg_hidden = total_completion / len(players) if players else 0
        
        if avg_hidden >= 0.85:
            completion_rating = "SS"
            completion_reason = "Mọi người hoàn thành xuất sắc"
        elif avg_hidden >= 0.75:
            completion_rating = "S"
            completion_reason = "Nhóm hoàn thành tuyệt vời"
        elif avg_hidden >= 0.6:
            completion_rating = "A"
            completion_reason = "Nhóm hoàn thành tốt"
        elif avg_hidden >= 0.45:
            completion_rating = "B"
            completion_reason = "Nhóm hoàn thành khá"
        elif avg_hidden >= 0.3:
            completion_rating = "C"
            completion_reason = "Nhóm hoàn thành bình thường"
        elif avg_hidden >= 0.15:
            completion_rating = "D"
            completion_reason = "Nhóm hoàn thành yếu"
        else:
            completion_rating = "F"
            completion_reason = "Nhóm hoàn thành thất bại"
        
        # Remove hidden score from display
        for p in players_eval:
            del p['_hidden_score']
        
        return {
            "game_code": game['game_code'],
            "scenario": scenario_type,
            "completion_rating": completion_rating,
            "completion_reason": completion_reason,
            "players": players_eval
        }
    
    except Exception as e:
        print(f"❌ Error evaluating game: {e}")
        return None

def _calculate_player_rating(player: dict, objectives: list, game_id: str) -> tuple:
    """
    Calculate player rating with HIDDEN criteria.
    Only shows HP/Sanity in reason, but rating is based on:
    - Base score: HP/100 + Sanity/100 (visible)
    - Hidden criteria: stats, items found (agi, acc), objectives (invisible)
    
    Returns: (rating_str, hidden_score_0_to_1)
    """
    hp = player['hp']
    sanity = player['sanity']
    agi = player['agi']
    acc = player['acc']
    
    # Visible metrics (show to player)
    visible_score = (hp + sanity) / 200  # 0-1
    
    # Hidden metrics (not shown)
    agi_score = min(agi / 100, 1.0)  # Agility = 0-1
    acc_score = min(acc / 100, 1.0)  # Accuracy = 0-1
    
    # Hidden criteria for A→SS
    # Survive + high stats = bonus
    if hp > 0 and sanity > 30 and (agi > 60 or acc > 60):
        hidden_bonus = 0.2  # +0.2 for A→S→SS
    elif hp > 50 and sanity > 50:
        hidden_bonus = 0.1
    elif hp > 0:
        hidden_bonus = 0.05
    else:
        hidden_bonus = 0
    
    # Combine: visible (weight 0.5) + hidden (weight 0.5)
    final_score = (visible_score * 0.5) + ((agi_score + acc_score) / 2 * 0.3) + (hidden_bonus * 0.2)
    final_score = min(max(final_score, 0), 1.0)
    
    # Determine rating from final score
    if final_score >= 0.92:
        rating = "SS"
    elif final_score >= 0.82:
        rating = "S"
    elif final_score >= 0.72:
        rating = "A"
    elif final_score >= 0.56:
        rating = "B"
    elif final_score >= 0.40:
        rating = "C"
    elif final_score >= 0.24:
        rating = "D"
    else:
        rating = "F"
    
    return rating, final_score

def _fallback_evaluation(game: dict, players: list) -> dict:
    """Fallback evaluation when needed."""
    players_eval = []
    total_score = 0
    
    for player in players:
        rating, score = _calculate_player_rating(player, [], "")
        
        hp = player['hp']
        sanity = player['sanity']
        
        if hp <= 0:
            reason = "Bị tiêu diệt trong trận đánh"
        elif sanity <= 20:
            reason = "Bị sợ hãi, mất tinh thần"
        elif hp <= 30:
            reason = f"Sống sót nhưng bị thương nặng (HP: {hp}/100)"
        elif sanity <= 40:
            reason = f"Sống sót với tinh thần tổn thương (Sanity: {sanity}/100)"
        else:
            reason = f"Sống sót tốt (HP: {hp}/100, Sanity: {sanity}/100)"
        
        players_eval.append({
            "user_id": player['user_id'],
            "rating": rating,
            "reason": reason
        })
        total_score += score
    
    # Overall rating
    avg_score = total_score / len(players) if players else 0
    if avg_score >= 0.85:
        completion_rating = "SS"
    elif avg_score >= 0.75:
        completion_rating = "S"
    elif avg_score >= 0.6:
        completion_rating = "A"
    elif avg_score >= 0.45:
        completion_rating = "B"
    elif avg_score >= 0.3:
        completion_rating = "C"
    elif avg_score >= 0.15:
        completion_rating = "D"
    else:
        completion_rating = "F"
    
    return {
        "game_code": game['game_code'],
        "scenario": "",
        "completion_rating": completion_rating,
        "completion_reason": "Hoàn thành",
        "players": players_eval
    }

async def create_leaderboard_channel(
    guild: discord.Guild,
    category: discord.CategoryChannel,
    evaluation: dict,
    game_code: str,
    completion_reason: str = ""
) -> discord.TextChannel:
    """Create a leaderboard channel for completed game."""
    try:
        leaderboard_channel = await guild.create_text_channel(
            name=f"🏆-leaderboard-{game_code.lower()}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)
            },
            reason="Game completion leaderboard"
        )
        
        # Create leaderboard embed
        embed = discord.Embed(
            title=f"🏆 LEADERBOARD - {game_code}",
            description=f"Kịch bản: **{evaluation['scenario'].upper()}**",
            color=discord.Color.gold()
        )
        
        # Completion rating
        completion_rating = evaluation.get('completion_rating', 'C')
        completion_reason_eval = evaluation.get('completion_reason', '')
        if completion_reason:
            completion_reason_eval = completion_reason
        rating_emoji = _get_rating_emoji(completion_rating)
        
        embed.add_field(
            name=f"{rating_emoji} Đánh Giá Chung",
            value=f"**{completion_rating}**\n{completion_reason_eval}",
            inline=False
        )
        
        # Players ratings
        players_text = ""
        for i, player in enumerate(evaluation.get('players', []), 1):
            user_id = player['user_id']
            rating = player['rating']
            reason = player['reason']
            emoji = _get_rating_emoji(rating)
            
            players_text += f"{i}. <@{user_id}> {emoji} **{rating}**\n   _{reason}_\n"
        
        if players_text:
            embed.add_field(
                name="👥 Xếp Hạng Người Chơi",
                value=players_text,
                inline=False
            )
        
        embed.set_footer(text=f"Được đánh giá bởi AI Moderator")
        
        await leaderboard_channel.send(embed=embed)
        
        print(f"✅ [LEADERBOARD] Created: {leaderboard_channel.name}")
        return leaderboard_channel
    
    except Exception as e:
        print(f"❌ Error creating leaderboard channel: {e}")
        return None

def _get_rating_emoji(rating: str) -> str:
    """Get emoji for rating."""
    emoji_map = {
        "SS": "🌟",
        "S": "⭐",
        "A": "✨",
        "B": "👍",
        "C": "👌",
        "D": "⚠️",
        "F": "❌"
    }
    return emoji_map.get(rating, "❓")
