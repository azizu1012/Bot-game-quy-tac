"""
HORROR BOT - RECOVERY SERVICE
Tự động backup/restore game state khi server crash
"""

import json
import os
from datetime import datetime
from database import db_manager

BACKUP_DIR = "database/backups"

async def ensure_backup_dir():
    """Tạo thư mục backup nếu chưa tồn tại."""
    os.makedirs(BACKUP_DIR, exist_ok=True)

async def create_backup():
    """Tạo backup của tất cả active games + player data."""
    try:
        await ensure_backup_dir()
        
        # Get all active games
        games = await db_manager.execute_query(
            "SELECT * FROM active_games WHERE is_active = 1",
            fetchall=True
        )
        
        if not games:
            print("ℹ️ [BACKUP] No active games to backup")
            return
        
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "games": [],
            "players": []
        }
        
        for game in games:
            game_dict = dict(game)
            backup_data["games"].append(game_dict)
            
            # Get players for this game
            players = await db_manager.execute_query(
                "SELECT * FROM players WHERE game_id = ?",
                (game_dict['channel_id'],),
                fetchall=True
            )
            
            for player in players:
                player_dict = dict(player)
                player_dict['game_code'] = game_dict['game_code']
                backup_data["players"].append(player_dict)
        
        # Save backup
        backup_file = f"{BACKUP_DIR}/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ [BACKUP] Backup created: {backup_file}")
        return backup_file
        
    except Exception as e:
        print(f"❌ [BACKUP] Error creating backup: {e}")

async def restore_from_backup():
    """Khôi phục game state từ backup mới nhất."""
    try:
        await ensure_backup_dir()
        
        # Find latest backup
        backup_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_")])
        if not backup_files:
            print("ℹ️ [RECOVERY] No backup files found")
            return False
        
        latest_backup = os.path.join(BACKUP_DIR, backup_files[-1])
        
        with open(latest_backup, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        print(f"🔄 [RECOVERY] Restoring from: {latest_backup}")
        
        restored_count = 0
        
        # Restore games
        for game in backup_data.get("games", []):
            # Check if already exists
            existing = await db_manager.execute_query(
                "SELECT * FROM active_games WHERE channel_id = ?",
                (game['channel_id'],),
                fetchone=True
            )
            
            if not existing:
                await db_manager.execute_query(
                    """INSERT INTO active_games 
                       (channel_id, lobby_channel_id, dashboard_channel_id, host_id, 
                        game_creator_id, scenario_type, game_code, setup_by_admin_id, is_active) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (game['channel_id'], game['lobby_channel_id'], game['dashboard_channel_id'],
                     game['host_id'], game['game_creator_id'], game['scenario_type'],
                     game['game_code'], game['setup_by_admin_id'], game['is_active']),
                    commit=True
                )
                print(f"   ✅ Restored game: {game['game_code']}")
                restored_count += 1
        
        # Restore players
        for player in backup_data.get("players", []):
            existing = await db_manager.execute_query(
                "SELECT * FROM players WHERE user_id = ? AND game_id = ?",
                (player['user_id'], player['game_id']),
                fetchone=True
            )
            
            if not existing:
                await db_manager.execute_query(
                    """INSERT INTO players 
                       (user_id, game_id, background_id, background_name, background_description,
                        hp, sanity, agi, acc, current_location_id, private_channel_id, is_ready) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (player['user_id'], player['game_id'], player['background_id'],
                     player['background_name'], player['background_description'],
                     player['hp'], player['sanity'], player['agi'], player['acc'],
                     player['current_location_id'], player['private_channel_id'], player['is_ready']),
                    commit=True
                )
        
        print(f"✅ [RECOVERY] Restored {restored_count} games successfully")
        return True
        
    except Exception as e:
        print(f"❌ [RECOVERY] Error restoring backup: {e}")
        return False

async def cleanup_old_backups(keep_count=5):
    """Xóa backup cũ, chỉ giữ lại N file mới nhất."""
    try:
        await ensure_backup_dir()
        
        backup_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("backup_")])
        
        if len(backup_files) > keep_count:
            for old_file in backup_files[:-keep_count]:
                os.remove(os.path.join(BACKUP_DIR, old_file))
                print(f"🗑️ [BACKUP] Deleted old backup: {old_file}")
    
    except Exception as e:
        print(f"⚠️ [BACKUP] Error cleaning backups: {e}")
