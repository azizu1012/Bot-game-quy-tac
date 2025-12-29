"""Service để generate kịch bản động từ AI."""

import asyncio
from services import llm_service


async def generate_scenario_title(scenario_type: str, num_players: int) -> str:
    """Generate một tiêu đề kịch bản từ AI.
    
    Args:
        scenario_type: 'hotel' hoặc 'hospital'
        num_players: số lượng người chơi
        
    Returns:
        str: Tiêu đề kịch bản
    """
    keywords = [scenario_type, "kinh dị", "bí ẩn", "sinh tồn"]
    
    try:
        title = await llm_service.describe_scene(keywords)
        return title if title else f"Thảm Kịch Tại {scenario_type.title()}"
    except Exception as e:
        print(f"⚠️ Lỗi generate title: {e}")
        return f"Thảm Kịch Tại {scenario_type.title()}"


async def generate_turn_intro(scenario_type: str, turn_number: int, player_count: int) -> str:
    """Generate intro cho mỗi turn - giới thiệu bối cảnh nhưng không tiết lộ quái vật.
    
    Args:
        scenario_type: loại kịch bản
        turn_number: số lượt hiện tại
        player_count: số người chơi
        
    Returns:
        str: Đoạn intro từ AI
    """
    # Keywords chỉ mô tả bối cảnh, không tiết lộ quái vật
    keywords = [scenario_type, "bí ẩn", "nguy hiểm", "tối tối", "lạnh lẽo", f"lượt {turn_number}"]
    
    try:
        intro = await llm_service.describe_scene(keywords)
        # Đảm bảo intro không chứa từ "quái vật" hoặc "ghost"
        intro = intro.replace("quái vật", "cái gì đó").replace("ghost", "thứ gì đó")
        return intro if intro else f"Bạn đặt chân vào {scenario_type}... Không gian im lặm, chỉ có tiếng bước chân của mình."
    except Exception as e:
        print(f"⚠️  Lỗi generate intro: {e}")
        return f"Bạn đặt chân vào {scenario_type}... Không gian im lặm, chỉ có tiếng bước chân của mình."


async def generate_death_message(player_name: str, scenario_type: str) -> str:
    """Generate thông báo khi người chơi chết.
    
    Args:
        player_name: tên người chơi
        scenario_type: loại kịch bản
        
    Returns:
        str: Thông báo tử vong
    """
    keywords = [player_name, scenario_type, "chết", "tuyệt vọng", "tối tăm"]
    
    try:
        message = await llm_service.describe_scene(keywords)
        return message if message else f"{player_name} đã gặp số phận tự định..."
    except Exception as e:
        print(f"⚠️ Lỗi generate death message: {e}")
        return f"{player_name} đã gặp số phận tự định..."


async def generate_room_description(room_type: str, scenario_type: str) -> str:
    """Generate mô tả cho một phòng dựa trên loại phòng.
    
    Args:
        room_type: loại phòng ('room', 'stairwell_up', 'stairwell_down')
        scenario_type: loại kịch bản
        
    Returns:
        str: Mô tả phòng
    """
    room_keywords = {
        'room': ['phòng', 'tối tối', 'cũ kỹ', 'bí ẩn'],
        'stairwell_up': ['cầu thang lên', 'tối tăm', 'có vẻ an toàn hơn'],
        'stairwell_down': ['cầu thang xuống', 'vô tận', 'ác quỷ']
    }
    
    keywords = room_keywords.get(room_type, ['phòng', 'kinh dị']) + [scenario_type]
    
    try:
        description = await llm_service.describe_scene(keywords)
        return description if description else f"Một {room_type.replace('_', ' ')} trong {scenario_type}."
    except Exception as e:
        print(f"⚠️ Lỗi generate room description: {e}")
        return f"Một {room_type.replace('_', ' ')} trong {scenario_type}."
