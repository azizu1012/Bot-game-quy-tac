"""Service để random background và generate chỉ số RPG cho người chơi."""

import json
import random
import os
from pathlib import Path
from services import llm_service

BACKGROUNDS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    "data", 
    "backgrounds.json"
)

def load_backgrounds():
    """Tải danh sách background từ file JSON."""
    try:
        with open(BACKGROUNDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file backgrounds.json tại {BACKGROUNDS_FILE}")
        return []

def generate_random_background():
    """Random một background từ danh sách có sẵn.
    
    Returns:
        dict: {
            'id': str,
            'name': str,
            'description': str,
            'stats': {
                'hp': int,
                'sanity': int,
                'agi': int,
                'acc': int
            }
        }
    """
    backgrounds = load_backgrounds()
    if not backgrounds:
        # Fallback nếu không load được file
        return {
            'id': 'survivor',
            'name': 'Người Sống Sót',
            'description': 'Bạn là một sinh viên thường thôi.',
            'stats': {'hp': 100, 'sanity': 100, 'agi': 50, 'acc': 50}
        }
    
    return random.choice(backgrounds)

def apply_background_stats(base_stats: dict, background: dict) -> dict:
    """Áp dụng stats từ background vào base stats.
    
    Args:
        base_stats: dict với keys: hp, sanity, agi, acc
        background: dict chứa stats từ background
        
    Returns:
        dict: merged stats
    """
    result = base_stats.copy()
    if 'stats' in background:
        result.update(background['stats'])
    return result

def randomize_stats_with_variation(base_stats: dict, variation_percent: float = 10.0) -> dict:
    """Thêm variation ngẫu nhiên vào chỉ số (±variation_percent).
    
    Args:
        base_stats: dict với keys: hp, sanity, agi, acc
        variation_percent: % biến đổi (default 10%)
        
    Returns:
        dict: modified stats
    """
    result = base_stats.copy()
    for key in ['hp', 'sanity', 'agi', 'acc']:
        if key in result:
            # Tính variation
            variation = int(result[key] * variation_percent / 100)
            offset = random.randint(-variation, variation)
            # Đảm bảo stats không âm và hợp lý
            result[key] = max(10, min(200, result[key] + offset))
    return result

async def generate_background_description(background_name: str, scenario_type: str) -> str:
    """Generate background description (simplified - no LLM for speed).
    
    Args:
        background_name: Tên background (vd: 'Police Officer')
        scenario_type: Loại kịch bản (vd: 'hotel', 'hospital')
        
    Returns:
        str: Đoạn mô tả sinh động
    """
    # Simplified descriptions - no LLM call to speed up game creation
    descriptions = {
        "Police Officer": f"Cảnh sát, huấn luyện tốt, quen với nguy hiểm, nhưng {scenario_type} vẫn vượt xa tưởng tượng.",
        "Doctor": f"Bác sĩ, khám phá sự sống và cái chết, nhưng {scenario_type} là thứ gì đó hoàn toàn khác.",
        "Student": f"Sinh viên, trẻ trung nhưng không chuẩn bị, {scenario_type} sẽ thử thách lòng can đảm.",
        "Journalist": f"Nhà báo, tò mò và thích tìm sự thật, nhưng {scenario_type} ẩn giấu những bí mật kinh hoàng.",
        "Survivor": f"Người sống sót, đã trải qua nhiều khó khăn, {scenario_type} là thách thức tiếp theo."
    }
    
    return descriptions.get(background_name, f"{background_name} bước vào {scenario_type} với những hy vọng mong manh.")

async def create_player_profile(scenario_type: str) -> dict:
    """Tạo profile hoàn chỉnh cho một người chơi mới.
    
    Returns:
        dict: {
            'background_id': str,
            'background_name': str,
            'background_description': str,
            'hp': int,
            'sanity': int,
            'agi': int,
            'acc': int
        }
    """
    # Random background
    background = generate_random_background()
    
    # Merge stats
    base_stats = {'hp': 100, 'sanity': 100, 'agi': 50, 'acc': 50}
    merged_stats = apply_background_stats(base_stats, background)
    
    # Thêm variation
    final_stats = randomize_stats_with_variation(merged_stats, variation_percent=15.0)
    
    # Generate description từ AI
    description = await generate_background_description(background['name'], scenario_type)
    
    profile = {
        'background_id': background['id'],
        'background_name': background['name'],
        'background_description': description,
        'hp': final_stats['hp'],
        'sanity': final_stats['sanity'],
        'agi': final_stats['agi'],
        'acc': final_stats['acc']
    }
    
    return profile
