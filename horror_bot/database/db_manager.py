import aiosqlite
import os

# --- CẤU HÌNH ĐƯỜNG DẪN TUYỆT ĐỐI (QUAN TRỌNG) ---
# Lấy đường dẫn thư mục chứa file db_manager.py (tức là thư mục database/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# File DB sẽ nằm ở thư mục cha (horror_bot/)
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "horror_bot.db")

# File Schema nằm ngay trong thư mục database/
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

async def get_db_connection():
    """Get a database connection with row factory set to aiosqlite.Row."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

async def setup_database():
    """Hàm này sẽ đọc file schema.sql và tạo bảng"""
    print(f"🛠️ Đang kiểm tra Database tại: {DB_PATH}")
    print(f"📄 Đang đọc Schema tại: {SCHEMA_PATH}")

    if not os.path.exists(SCHEMA_PATH):
        print(f"❌ LỖI NGHIÊM TRỌNG: Không tìm thấy file schema.sql tại {SCHEMA_PATH}")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema = f.read()
            
            # Kiểm tra file có rỗng không
            if not schema.strip():
                print("❌ LỖI: File schema.sql bị rỗng! Hãy copy nội dung SQL vào.")
                return

            try:
                await db.executescript(schema)
                await db.commit()
                print("✅ Đã chạy lệnh tạo bảng thành công.")
            except Exception as e:
                print(f"❌ Lỗi SQL khi tạo bảng: {e}")

async def execute_query(query, params=(), commit=False, fetchone=False, fetchall=False):
    """Hàm tiện ích để chạy query SQL an toàn (trả về dict, không phải Row)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            result = None
            if fetchone:
                row = await cursor.fetchone()
                result = dict(row) if row else None
            elif fetchall:
                rows = await cursor.fetchall()
                result = [dict(row) for row in rows] if rows else []
            
            if commit:
                await db.commit()
            return result

# ===== HELPER FUNCTIONS FOR GAME MANAGEMENT =====

async def get_player_current_game(user_id: int) -> int | None:
    """Kiểm tra người chơi hiện đang tham gia game nào (nếu có)."""
    result = await execute_query(
        """SELECT game_id FROM players 
           WHERE user_id = ? 
           AND game_id IN (SELECT channel_id FROM active_games WHERE is_active = 1)""",
        (user_id,),
        fetchone=True
    )
    return result['game_id'] if result else None

async def check_player_in_game(user_id: int, game_id: int) -> bool:
    """Kiểm tra người chơi đã trong game này chưa."""
    result = await execute_query(
        "SELECT 1 FROM players WHERE user_id = ? AND game_id = ?",
        (user_id, game_id),
        fetchone=True
    )
    return result is not None

async def get_waiting_room_confirmations(game_id: int) -> dict:
    """Lấy số người đã confirm và chưa confirm trong waiting room."""
    players = await execute_query(
        "SELECT user_id, waiting_room_confirmed FROM players WHERE game_id = ?",
        (game_id,),
        fetchall=True
    )
    confirmed = sum(1 for p in players if p.get('waiting_room_confirmed'))
    total = len(players)
    return {"confirmed": confirmed, "total": total, "players": players}

async def get_game_creator(game_id: int) -> int | None:
    """Lấy ID của người tạo game."""
    result = await execute_query(
        "SELECT game_creator_id FROM active_games WHERE channel_id = ?",
        (game_id,),
        fetchone=True
    )
    return result['game_creator_id'] if result else None

async def get_game_setup(guild_id: int) -> dict | None:
    """Lấy game setup config cho guild."""
    result = await execute_query(
        "SELECT * FROM game_setups WHERE guild_id = ? LIMIT 1",
        (guild_id,),
        fetchone=True
    )
    return result

async def get_end_game_votes(game_id: int) -> dict:
    """Lấy số người vote end game."""
    players = await execute_query(
        "SELECT user_id, voted_end_game FROM players WHERE game_id = ?",
        (game_id,),
        fetchall=True
    )
    voted = sum(1 for p in players if p.get('voted_end_game'))
    total = len(players)
    return {"voted": voted, "total": total, "ratio": voted / total if total > 0 else 0}

async def cleanup_game(game_id: int):
    """Xóa sạch tất cả dữ liệu liên quan đến game."""
    await execute_query("DELETE FROM players WHERE game_id = ?", (game_id,), commit=True)
    await execute_query("DELETE FROM game_maps WHERE game_id = ?", (game_id,), commit=True)
    await execute_query("DELETE FROM game_rules WHERE game_id = ?", (game_id,), commit=True)
    await execute_query("DELETE FROM game_context WHERE game_id = ?", (game_id,), commit=True)
    await execute_query("DELETE FROM active_games WHERE channel_id = ?", (game_id,), commit=True)

# ===== HIDDEN RULES & DISCOVERY SYSTEM =====

async def get_game_rules(game_id: int, is_public: bool = True) -> list:
    """Lấy danh sách rules (public hoặc hidden)."""
    result = await execute_query(
        "SELECT * FROM game_rules WHERE game_id = ? AND is_public = ?",
        (game_id, 1 if is_public else 0),
        fetchall=True
    )
    return result

async def discover_hidden_rule(user_id: int, game_id: int, rule_id: int) -> bool:
    """Mark hidden rule as discovered by player."""
    import json
    player = await execute_query(
        "SELECT discovered_hidden_rules FROM players WHERE user_id = ? AND game_id = ?",
        (user_id, game_id),
        fetchone=True
    )
    
    if not player:
        return False
    
    discovered = json.loads(player.get('discovered_hidden_rules', '[]'))
    if rule_id not in discovered:
        discovered.append(rule_id)
        await execute_query(
            "UPDATE players SET discovered_hidden_rules = ? WHERE user_id = ? AND game_id = ?",
            (json.dumps(discovered), user_id, game_id),
            commit=True
        )
    return True

async def get_player_discovered_rules(user_id: int, game_id: int) -> list:
    """Lấy danh sách hidden rules mà player đã khám phá."""
    player = await execute_query(
        "SELECT discovered_hidden_rules FROM players WHERE user_id = ? AND game_id = ?",
        (user_id, game_id),
        fetchone=True
    )
    if not player:
        return []
    
    import json
    return json.loads(player.get('discovered_hidden_rules', '[]'))

# ===== SANITY & PENALTY SYSTEM =====

async def update_player_sanity(user_id: int, game_id: int, delta: int) -> int:
    """Thay đổi sanity của player, return new sanity value."""
    player = await execute_query(
        "SELECT sanity FROM players WHERE user_id = ? AND game_id = ?",
        (user_id, game_id),
        fetchone=True
    )
    
    if not player:
        return 0
    
    new_sanity = max(0, min(100, player['sanity'] + delta))
    await execute_query(
        "UPDATE players SET sanity = ? WHERE user_id = ? AND game_id = ?",
        (new_sanity, user_id, game_id),
        commit=True
    )
    return new_sanity

async def get_threat_level(game_id: int) -> int:
    """Lấy mức độ nguy hiểm hiện tại (0=Safe, 1=Danger, 2=Critical)."""
    context = await execute_query(
        "SELECT current_threat_level FROM game_context WHERE game_id = ?",
        (game_id,),
        fetchone=True
    )
    return context['current_threat_level'] if context else 0

async def update_threat_level(game_id: int, level: int):
    """Cập nhật mức độ nguy hiểm của game."""
    await execute_query(
        "UPDATE game_context SET current_threat_level = ? WHERE game_id = ?",
        (level, game_id),
        commit=True
    )

# ===== ACTION SUCCESS CALCULATION =====

def calculate_action_success(player_stat: int, sanity: int, base_success_rate: float) -> bool:
    """Tính toán xác suất thành công của action dựa trên stat, sanity và base_success_rate.
    
    Args:
        player_stat: Stat của player (acc, agi, etc.)
        sanity: Sanity hiện tại (0-100)
        base_success_rate: Tỷ lệ thành công cơ bản (0.0-1.0)
    
    Returns:
        True nếu action thành công
    """
    import random
    
    # Sanity modifier: Low sanity = Lower success
    # At sanity 0: -60% success rate
    # At sanity 100: 0% modifier
    sanity_modifier = (sanity / 100.0) - 0.4
    
    # Stat modifier: Higher stat = Higher success
    stat_modifier = (player_stat / 100.0) * 0.3
    
    final_success_rate = min(max(base_success_rate + sanity_modifier + stat_modifier, 0.1), 0.95)
    return random.random() < final_success_rate


# ===== V4 HELPERS (Free-form Actions) =====

async def get_players_at_location(game_id: str, location_id: str) -> list:
    """Get all players at a specific location."""
    result = await execute_query(
        """SELECT user_id, background_name, private_channel_id, hp 
           FROM players WHERE game_id = ? AND current_location_id = ? AND hp > 0""",
        (game_id, location_id),
        fetchall=True
    )
    return result


async def get_game_by_id(game_id: str) -> dict:
    """Get game info by game_id (UUID-based)."""
    result = await execute_query(
        """SELECT channel_id, lobby_channel_id, dashboard_channel_id, 
                  dashboard_message_id, scenario_type, is_active
           FROM active_games WHERE channel_id = ?""",
        (game_id,),
        fetchone=True
    )
    return result


async def update_player_stats(
    user_id: int,
    game_id: str,
    hp_change: int = 0,
    sanity_change: int = 0,
    new_location_id: str = None,
    new_inventory: list = None
) -> dict:
    """Update player stats atomically."""
    import json
    
    # Get current stats
    player = await execute_query(
        """SELECT hp, sanity, current_location_id, inventory 
           FROM players WHERE user_id = ? AND game_id = ?""",
        (user_id, game_id),
        fetchone=True
    )
    
    if not player:
        return None
    
    # Calculate new values
    new_hp = max(0, min(100, player['hp'] + hp_change))
    new_sanity = max(0, min(100, player['sanity'] + sanity_change))
    location = new_location_id if new_location_id else player['current_location_id']
    inventory = json.dumps(new_inventory) if new_inventory else player['inventory']
    
    # Update database
    await execute_query(
        """UPDATE players SET hp = ?, sanity = ?, current_location_id = ?, inventory = ?
           WHERE user_id = ? AND game_id = ?""",
        (new_hp, new_sanity, location, inventory, user_id, game_id),
        commit=True
    )
    
    return {
        'hp': new_hp,
        'sanity': new_sanity,
        'location_id': location,
        'inventory': new_inventory
    }


async def append_to_llm_history(user_id: int, game_id: str, role: str, content: str):
    """Append message to LLM conversation history (keep last 10)."""
    import json
    
    player = await execute_query(
        "SELECT llm_conversation_history FROM players WHERE user_id = ? AND game_id = ?",
        (user_id, game_id),
        fetchone=True
    )
    
    if not player:
        return
    
    history = json.loads(player['llm_conversation_history']) if player['llm_conversation_history'] else []
    
    # Append new message
    history.append({"role": role, "content": content})
    
    # Keep only last 10 messages to save memory
    history = history[-10:]
    
    await execute_query(
        "UPDATE players SET llm_conversation_history = ? WHERE user_id = ? AND game_id = ?",
        (json.dumps(history), user_id, game_id),
        commit=True
    )


async def get_llm_history(user_id: int, game_id: str) -> list:
    """Get player's LLM conversation history."""
    import json
    
    player = await execute_query(
        "SELECT llm_conversation_history FROM players WHERE user_id = ? AND game_id = ?",
        (user_id, game_id),
        fetchone=True
    )
    
    if not player:
        return []
    
    return json.loads(player['llm_conversation_history']) if player['llm_conversation_history'] else []


async def record_encounter(game_id: str, location_id: str, player_ids: list, encounter_text: str):
    """Record player encounter in database."""
    import json
    
    await execute_query(
        """INSERT INTO player_encounters (game_id, location_id, player_ids, encounter_text)
           VALUES (?, ?, ?, ?)""",
        (game_id, location_id, json.dumps(player_ids), encounter_text),
        commit=True
    )