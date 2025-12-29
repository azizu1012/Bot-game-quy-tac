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
Bạn là quản trò game kinh dị. Hãy viết một đoạn văn mô tả ngắn (dưới 50 từ) dựa trên các từ khóa: {', '.join(keywords)}. Giọng văn u ám, đáng sợ.<|im_end|>
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