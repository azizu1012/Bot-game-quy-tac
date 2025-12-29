import os
from huggingface_hub import hf_hub_download

def download_model():
    # Đây là repo chuẩn của Qwen 2.5 GGUF, bạn không cần tìm nữa
    REPO_ID = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
    FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    
    # Thư mục lưu
    MODEL_DIR = "./models"
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)

    print(f"⬇️ Đang tải {FILENAME} từ HuggingFace...")
    print("☕ Việc này có thể mất vài phút tùy mạng VPS...")
    
    model_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=FILENAME,
        local_dir=MODEL_DIR,
        local_dir_use_symlinks=False
    )
    
    print(f"\n✅ Đã tải xong! Đường dẫn model: {model_path}")
    print("👉 Hãy copy đường dẫn trên vào file .env")

if __name__ == "__main__":
    download_model()