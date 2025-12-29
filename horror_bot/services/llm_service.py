import asyncio
import os
from dotenv import load_dotenv
try:
    from llama_cpp import Llama
except ImportError:
    print("Lỗi: Chưa cài llama-cpp-python. Hãy chạy pip install -r requirements.txt")
    Llama = None

load_dotenv()

LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH")
n_threads = int(os.getenv("LLM_N_THREADS", "2"))
n_ctx = int(os.getenv("LLM_CONTEXT_SIZE", "4096"))

# Global model instance
_llm = None

def load_llm():
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
            n_gpu_layers=0, # Chạy thuần CPU
            verbose=False
        )
        print("✅ LLM Load thành công!")
        return True
    except Exception as e:
        print(f"❌ Lỗi load model: {e}")
        return False

async def describe_scene(keywords: list[str]) -> str:
    if _llm is None:
        return "Không gian tĩnh mịch... (AI chưa load)"

    # Prompt tối ưu cho Qwen Instruct
    prompt = f"""<|im_start|>system
Bạn là quản trò game kinh dí. Hãy viết một đoạn văn mô tả ngắn (dưới 50 từ) dựa trên các từ khóa: {', '.join(keywords)}. Giọng văn u ám, đáng sợ.<|im_end|>
<|im_start|>user
Mô tả cảnh này.<|im_end|>
<|im_start|>assistant
"""

    loop = asyncio.get_running_loop()
    
    # Chạy trong thread pool để không chặn bot Discord
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

async def describe_scene_stream(keywords: list[str], callback=None) -> str:
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
        
        # Nếu có callback, gọi callback với từng câu
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