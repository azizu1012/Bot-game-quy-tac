"""
HORROR BOT - LLM SERVICE (Per-user Dungeon Master)
Unified service for all LLM inference - turn narratives, per-player actions, encounters
"""

import asyncio
import json
import os
from pathlib import Path
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

# Prompt loading utility
_prompt_cache = {}
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
DATA_DIR = Path(__file__).parent.parent / "data"

def get_prompt(prompt_name: str, **kwargs) -> str:
    """Loads a prompt from a file, caches it, and formats it with kwargs."""
    if prompt_name not in _prompt_cache:
        prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                _prompt_cache[prompt_name] = f.read()
        except FileNotFoundError:
            print(f"❌ Lỗi: Không tìm thấy file prompt: {prompt_path}")
            return "" # Return empty string if prompt not found
            
    return _prompt_cache[prompt_name].format(**kwargs)

def read_data_file(file_path: str) -> str | None:
    """Reads a text file from the data directory."""
    full_path = DATA_DIR / file_path
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"❌ Lỗi: Không tìm thấy data file: {full_path}")
        return None


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

    prompt = get_prompt(
        "process_player_action",
        system_prompt=system_prompt,
        messages_text=messages_text,
        action_text=action_text
    )
    if not prompt:
        return json.dumps({
            "success": False,
            "description": "Lỗi: Không tìm thấy file prompt.",
            "hp_change": 0,
            "sanity_change": 0,
            "new_location_id": "same",
            "discovered_items": []
        })

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

    prompt = get_prompt(
        "generate_encounter",
        scenario_type=scenario_type,
        player_name=player_name,
        action_description=action_description,
        other_players=', '.join(other_players)
    )
    if not prompt:
        return f"Bạn gặp {', '.join(other_players)} trong tối tối..."

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

    prompt = get_prompt("describe_scene", keywords=', '.join(keywords))
    if not prompt:
        return "Không gian tĩnh mịch... (AI chưa load)"

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

    prompt = get_prompt("describe_scene", keywords=', '.join(keywords))
    if not prompt:
        return "Không gian tĩnh mịch... (AI chưa load)"

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


async def generate_dark_rules(scenario_type: str) -> dict:
    """Generate a set of dark rules for the game scenario like Chinese novels."""
    default_response = {"public_rules": [], "hidden_rules": []}
    if _llm is None:
        print("⚠️ LLM not loaded, returning empty rules.")
        return default_response

    prompt = get_prompt("generate_dark_rules", scenario_type=scenario_type)
    if not prompt:
        return default_response

    loop = asyncio.get_running_loop()
    
    def run_inference():
        try:
            output = _llm(
                prompt,
                max_tokens=1500,  # Increased token limit for JSON output
                stop=["<|im_end|>", "```"],
                echo=False,
                temperature=0.8
            )
            raw_text = output['choices'][0]['text'].strip()
            
            # Find the JSON block
            json_start = raw_text.find('{')
            json_end = raw_text.rfind('}') + 1
            if json_start == -1 or json_end == 0:
                print(f"❌ Lỗi: Không tìm thấy JSON trong output của LLM.\nOutput: {raw_text}")
                return default_response

            json_text = raw_text[json_start:json_end]
            
            # Parse the JSON
            parsed_json = json.loads(json_text)
            
            # Validate structure
            if "public_rules" not in parsed_json or "hidden_rules" not in parsed_json:
                print(f"❌ Lỗi: JSON output thiếu key 'public_rules' hoặc 'hidden_rules'.\nOutput: {json_text}")
                return default_response
            
            return parsed_json

        except json.JSONDecodeError as e:
            print(f"❌ Lỗi giải mã JSON: {e}\nRaw text: {raw_text}")
            return default_response
        except Exception as e:
            print(f"❌ Lỗi không xác định trong generate_dark_rules: {e}")
            return default_response

    return await loop.run_in_executor(None, run_inference)


async def generate_waiting_room_message(num_players: int, total_slots: int = 8) -> str:
    """Generate a natural greeting for waiting room."""
    if _llm is None:
        return f"Đang chờ đủ người tham gia... ({num_players}/{total_slots})"

    prompt = get_prompt(
        "generate_waiting_room_message",
        num_players=num_players,
        total_slots=total_slots
    )
    if not prompt:
        return f"Đang chờ đủ người tham gia... ({num_players}/{total_slots})"

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
    """Generate a simple greeting when creating game room by reading from a file."""
    greeting = read_data_file(f"lore/{scenario_type}/greeting.txt")
    return greeting or f"📍 Phòng {scenario_type} đợi bạn khám phá..."


async def generate_world_lore(scenario_type: str) -> str:
    """Generate detailed world lore for the scenario (can be long, will be chunked)."""
    # Get fallback lore from file
    fallback_lore = read_data_file(f"lore/{scenario_type}/lore.txt") or "Thế giới bí ẩn... (Không tìm thấy file lore)"
    
    # If LLM is not available, return fallback
    if _llm is None:
        return fallback_lore

    # Prepare reference lore for the prompt
    reference_lore = f"\nTham khảo: {fallback_lore[:150]}"

    # Get prompt from file
    prompt = get_prompt(
        "generate_world_lore",
        scenario_type=scenario_type,
        reference_lore=reference_lore
    )
    
    if not prompt: # Handle case where prompt file is missing
        return fallback_lore

    loop = asyncio.get_running_loop()
    
    def run_inference():
        try:
            output = _llm(
                prompt,
                max_tokens=500,
                stop=["<|im_end|>"],
                echo=False,
                temperature=0.7
            )
            result = output['choices'][0]['text'].strip()
            # If result looks like a refusal, return fallback
            if len(result) < 50 or "không thể" in result.lower() or "xin lỗi" in result.lower():
                return fallback_lore
            return result
        except Exception as e:
            print(f"⚠️ LLM error in generate_world_lore: {e}")
            return fallback_lore

    return await loop.run_in_executor(None, run_inference)


async def check_rule_violation(hidden_rules: list, action_text: str, action_description: str) -> dict:
    """Checks if a player's action violates any of the hidden rules."""
    default_response = {"violated": False, "reason": "Lỗi hệ thống phán xét."}
    if _llm is None or not hidden_rules:
        return default_response

    # Format hidden rules into a numbered list string
    rules_text = ""
    for i, rule in enumerate(hidden_rules, 1):
        rules_text += f"{i}. {rule['rule_text']}\n"

    prompt = get_prompt(
        "check_rule_violation",
        hidden_rules=rules_text,
        action_text=action_text,
        action_description=action_description
    )
    if not prompt:
        return default_response

    loop = asyncio.get_running_loop()

    def run_inference():
        try:
            output = _llm(
                prompt,
                max_tokens=300,
                stop=["<|im_end|>", "```"],
                echo=False,
                temperature=0.2  # Low temperature for logical reasoning
            )
            raw_text = output['choices'][0]['text'].strip()

            # Find the JSON block
            json_start = raw_text.find('{')
            json_end = raw_text.rfind('}') + 1
            if json_start == -1 or json_end == 0:
                print(f"❌ Lỗi: [Rule Check] Không tìm thấy JSON trong output.\nOutput: {raw_text}")
                return default_response

            json_text = raw_text[json_start:json_end]
            return json.loads(json_text)

        except json.JSONDecodeError as e:
            print(f"❌ Lỗi: [Rule Check] Giải mã JSON thất bại: {e}\nRaw text: {raw_text}")
            return default_response
        except Exception as e:
            print(f"❌ Lỗi không xác định trong check_rule_violation: {e}")
            return default_response

    return await loop.run_in_executor(None, run_inference)
