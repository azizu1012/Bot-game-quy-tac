"""
HORROR BOT - LLM SERVICE (Per-user Dungeon Master)
Unified service for all LLM inference - turn narratives, per-player actions, encounters
"""

import asyncio
import json
import os
from dotenv import load_dotenv

try:
    from llama_cpp import Llama
except ImportError:
    print("❌ Lỗi: Chưa cài llama-cpp-python. Hãy chạy pip install -r requirements.txt")
    Llama = None

load_dotenv()

LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH")
n_threads = int(os.getenv("LLM_N_THREADS", "4"))
n_ctx = int(os.getenv("LLM_CONTEXT_SIZE", "8192"))

# Global model instance
_llm = None

def load_llm():
    """Load Qwen model once for entire bot lifecycle."""
    global _llm
    if _llm is not None:
        return True

    if not LLM_MODEL_PATH or not os.path.exists(LLM_MODEL_PATH):
        print(f"❌ Không tìm thấy model tại: {LLM_MODEL_PATH}")
        print("👉 Hãy chạy python download_model.py trước.")
        return False

    try:
        print(f"🔄 Đang load model GGUF (Threads: {n_threads}, Context: {n_ctx})...")
        _llm = Llama(
            model_path=LLM_MODEL_PATH,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=0,  # Chạy thuần CPU
            verbose=False
        )
        print("✅ LLM Load thành công!")
        return True
    except Exception as e:
        print(f"❌ Lỗi load model: {e}")
        return False


# ============================================================================
# PER-PLAYER ACTION PROCESSING (Free-Form Text Actions)
# ============================================================================

async def process_player_action(
    action_text: str,
    system_prompt: str,
    conversation_history: list = None
) -> str:
    """
    Process free-form player action through LLM.
    Per-user isolated context prevents cross-player state leakage.
    
    Args:
        action_text: What the player typed (e.g., "Tôi tìm kiếm quanh phòng")
        system_prompt: Per-player system prompt (location desc, stats, inventory)
        conversation_history: Last 10 messages (rolling window)
    
    Returns:
        JSON string with action outcome:
        {
            "success": bool,
            "description": str,
            "hp_change": int,
            "sanity_change": int,
            "new_location_id": str,
            "discovered_items": [str]
        }
    """
    if _llm is None:
        return json.dumps({
            "success": False,
            "description": "Hệ thống AI chưa sẵn sàng.",
            "hp_change": 0,
            "sanity_change": 0,
            "new_location_id": "same",
            "discovered_items": []
        })

    if conversation_history is None:
        conversation_history = []

    # Build prompt with conversation history (last 5 messages for context)
    messages_text = ""
    for msg in conversation_history[-5:]:
        role = msg.get('role', 'user').upper()
        content = msg.get('content', '')
        messages_text += f"{role}: {content}\n"

    prompt = f"""<|im_start|>system
{system_prompt}<|im_end|>
{messages_text}
<|im_start|>user
{action_text}<|im_end|>
<|im_start|>assistant
"""

    loop = asyncio.get_running_loop()

    def run_inference():
        try:
            output = _llm(
                prompt,
                max_tokens=500,
                stop=["<|im_end|>"],
                echo=False,
                temperature=0.8
            )
            return output['choices'][0]['text'].strip()
        except Exception as e:
            print(f"❌ LLM inference error: {e}")
            return json.dumps({
                "success": False,
                "description": f"Lỗi: {e}",
                "hp_change": 0,
                "sanity_change": 0,
                "new_location_id": "same",
                "discovered_items": []
            })

    return await loop.run_in_executor(None, run_inference)


async def generate_encounter(
    action_description: str,
    player_name: str,
    other_players: list,
    scenario_type: str
) -> str:
    """
    Generate encounter scenario when 2+ players meet.
    Per-player isolated to avoid shared context issues.
    
    Args:
        action_description: What the first player did
        player_name: Name of first player
        other_players: List of other player names at location
        scenario_type: Scenario type for context
    
    Returns:
        Encounter description text (2-3 sentences)
    """
    if _llm is None:
        other_names = ", ".join(other_players)
        return f"Bạn gặp {other_names}. Cảm giác rất kỳ lạ..."

    prompt = f"""<|im_start|>system
Bạn là Dungeon Master kinh dí. Một tình huống gặp gỡ vừa xảy ra trong scenario {scenario_type}.

{player_name} vừa {action_description}

Các nhân vật khác tại đây: {', '.join(other_players)}

Hãy mô tả cảnh gặp gỡ bất ngờ này một cách kinh dí và sống động (2-3 câu). 
Tone: bí ẩn, căng thẳng, không chắc chắn.
<|im_end|>
<|im_start|>user
Mô tả cảnh gặp gỡ này<|im_end|>
<|im_start|>assistant
"""

    loop = asyncio.get_running_loop()

    def run_inference():
        try:
            output = _llm(
                prompt,
                max_tokens=200,
                stop=["<|im_end|>"],
                echo=False,
                temperature=0.9
            )
            return output['choices'][0]['text'].strip()
        except Exception as e:
            return f"Bạn gặp {', '.join(other_players)} trong tối tối..."

    return await loop.run_in_executor(None, run_inference)


# ============================================================================
# NARRATIVE GENERATION (Shared lore, rules, world-building)
# ============================================================================

async def describe_scene(keywords: list) -> str:
    """Generate scene description for narrative (optional, for global log)."""
    if _llm is None:
        return "Không gian tĩnh mịch... (AI chưa load)"

    prompt = f"""<|im_start|>system
Bạn là quản trò game kinh dí. Hãy viết một đoạn văn mô tả ngắn (dưới 50 từ) dựa trên các từ khóa: {', '.join(keywords)}. Giọng văn u ám, đáng sợ.<|im_end|>
<|im_start|>user
Mô tả cảnh này.<|im_end|>
<|im_start|>assistant
"""

    loop = asyncio.get_running_loop()
    
    def run_inference():
        output = _llm(
            prompt,
            max_tokens=150,
            stop=["<|im_end|>", "\n\n"],
            echo=False,
            temperature=0.7
        )
        return output['choices'][0]['text'].strip()

    return await loop.run_in_executor(None, run_inference)


async def describe_scene_stream(keywords: list, callback=None) -> str:
    """Generate scene description với streaming callback (gọi callback từng phần)."""
    if _llm is None:
        return "Không gian tĩnh mịch... (AI chưa load)"

    prompt = f"""<|im_start|>system
Bạn là quản trò game kinh dí. Hãy viết một đoạn văn mô tả ngắn (dưới 50 từ) dựa trên các từ khóa: {', '.join(keywords)}. Giọng văn u ám, đáng sợ.<|im_end|>
<|im_start|>user
Mô tả cảnh này.<|im_end|>
<|im_start|>assistant
"""

    loop = asyncio.get_running_loop()
    
    def run_inference():
        output = _llm(
            prompt,
            max_tokens=150,
            stop=["<|im_end|>", "\n\n"],
            echo=False,
            temperature=0.7
        )
        result = output['choices'][0]['text'].strip()
        
        if callback:
            sentences = result.split('. ')
            for i, sentence in enumerate(sentences):
                callback(sentence + ('.' if i < len(sentences) - 1 else ''))
        
        return result

    return await loop.run_in_executor(None, run_inference)


async def generate_dark_rules(scenario_type: str) -> str:
    """Generate a set of dark rules for the game scenario like Chinese novels."""
    if _llm is None:
        return "Không có quy tắc... (AI chưa load)"

    prompt = f"""<|im_start|>system
Bạn là tác giả tiểu thuyết kinh dị châu Á. Hãy tạo 3-4 quy tắc ma quái, u ám cho một trò chơi kinh dí trong scenario '{scenario_type}'. Viết dưới dạng danh sách với tone muốn rợn người, huyền bí, giống như các tiểu thuyết Trung Quốc cổ. Giữ ngắn gọn, mỗi quy tắc 1-2 câu.<|im_end|>
<|im_start|>user
Tạo những quy tắc quỷ dị cho scenario này.<|im_end|>
<|im_start|>assistant
"""

    loop = asyncio.get_running_loop()
    
    def run_inference():
        output = _llm(
            prompt,
            max_tokens=200,
            stop=["<|im_end|>", "\n\n\n"],
            echo=False,
            temperature=0.8
        )
        return output['choices'][0]['text'].strip()

    return await loop.run_in_executor(None, run_inference)


async def generate_waiting_room_message(num_players: int, total_slots: int = 8) -> str:
    """Generate a natural greeting for waiting room."""
    if _llm is None:
        return f"Đang chờ đủ người tham gia... ({num_players}/{total_slots})"

    prompt = f"""<|im_start|>system
Bạn là quản trò game kinh dí. Hãy viết một lời chào tự nhiên, huyền bí khoảng 2-3 câu để đón các người chơi tới phòng chờ. Tone: bí ẩn, đáng sợ. Sau đó thêm dòng yêu cầu: "Đang chờ {num_players}/{total_slots} người chơi xác nhận..."<|im_end|>
<|im_start|>user
Viết lời chào cho phòng chờ.<|im_end|>
<|im_start|>assistant
"""

    loop = asyncio.get_running_loop()
    
    def run_inference():
        output = _llm(
            prompt,
            max_tokens=150,
            stop=["<|im_end|>"],
            echo=False,
            temperature=0.7
        )
        return output['choices'][0]['text'].strip()

    return await loop.run_in_executor(None, run_inference)


async def generate_simple_greeting(scenario_type: str) -> str:
    """Generate a simple greeting when creating game room (preset, no LLM)."""
    greetings = {
        "asylum": "🏥 Một bệnh viện tâm thần lạnh lẽo, những chiếc giường trống... Bạn nghe tiếng động vang vang...",
        "factory": "🏭 Một nhà máy cũ kỹ, máy móc gỉ sét. Ánh sáng mờ từ cửa sổ vỡ...",
        "ghost_village": "👻 Một ngôi làng hoang vắng, nhà cửa đổ nát. Gió lạnh thổi qua...",
        "cursed_mansion": "🏰 Một lâu đài bị nguyền rủa. Bóng tối bao phủ mọi nơi...",
        "mine": "⛏️ Một mỏ than sâu thẳm, đầy vết nứt. Tiếng nước chảy từ dưới...",
        "prison": "⛓️ Một nhà tù cũ, những cell sắt gỉ sét. Âm thanh tiếng la hơ...",
        "abyss": "🌑 Một vực thẳm sâu, bóng tối không dứt. Bạn không biết dưới có gì...",
        "dead_forest": "🌲 Một khu rừng chết, cây cổ thụ héo úa. Vẫn còn mùi xác thối...",
        "research_hospital": "🔬 Một bệnh viện nghiên cứu bí mật, tấm kính đen kín...",
        "ghost_ship": "⛵ Một chiếc tàu bỏ hoang, sàn gỗ mục nát. Tiếng biển vang xa...",
    }
    
    return greetings.get(scenario_type, f"📍 Phòng {scenario_type} đợi bạn khám phá...")


async def generate_world_lore(scenario_type: str) -> str:
    """Generate detailed world lore for the scenario (can be long, will be chunked)."""
    if _llm is None:
        return "Thế giới bí ẩn... (AI chưa load)"

    prompt = f"""<|im_start|>system
Bạn là một tác giả tiểu thuyết kinh dị. Hãy viết lore chi tiết (300-400 từ) cho một thế giới kinh dí scenario '{scenario_type}'. 
Tone: huyền bí, đáng sợ, chi tiết, như các tiểu thuyết Trung Quốc cổ.
Mô tả: nguyên nhân bí ẩn, các quy tắc quỷ dị, những gì đang xảy ra, cảm giác khó chịu, các yếu tố siêu nhiên.
Viết bằng tiếng Việt, giữ âm hưởng ma quái.<|im_end|>
<|im_start|>user
Viết lore chi tiết cho scenario này.<|im_end|>
<|im_start|>assistant
"""

    loop = asyncio.get_running_loop()
    
    def run_inference():
        output = _llm(
            prompt,
            max_tokens=500,
            stop=["<|im_end|>"],
            echo=False,
            temperature=0.8
        )
        return output['choices'][0]['text'].strip()

    return await loop.run_in_executor(None, run_inference)
