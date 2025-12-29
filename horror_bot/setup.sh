#!/bin/bash

# Dừng script ngay nếu có lỗi xảy ra
set -e

# Màu sắc cho dễ nhìn
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== BẮT ĐẦU CÀI ĐẶT AUTOMATION CHO BOT GAME KINH DỊ ===${NC}"

# 1. Cài đặt thư viện hệ thống (Cần thiết để build llama-cpp tối ưu cho CPU Xeon)
echo -e "${CYAN}[1/5] Đang cập nhật hệ thống và cài build tools...${NC}"
if [ "$EUID" -ne 0 ]; then 
  echo "Vui lòng nhập mật khẩu sudo để cài đặt gói hệ thống:"
  sudo apt-get update && sudo apt-get install -y python3-venv python3-dev build-essential
else
  apt-get update && apt-get install -y python3-venv python3-dev build-essential
fi

# 2. Tạo môi trường ảo Python
echo -e "${CYAN}[2/5] Đang tạo môi trường ảo (venv)...${NC}"
if [ -d "venv" ]; then
    echo "Thư mục venv đã tồn tại. Bỏ qua bước tạo."
else
    python3 -m venv venv
    echo "Đã tạo venv."
fi

# Kích hoạt môi trường ảo
source venv/bin/activate

# 3. Cài đặt dependencies
echo -e "${CYAN}[3/5] Đang cài đặt thư viện Python...${NC}"
pip install --upgrade pip

# Cài các thư viện cơ bản
pip install discord.py python-dotenv huggingface-hub aiosqlite

# Cài llama-cpp-python với cờ biên dịch tối ưu cho CPU (QUAN TRỌNG)
echo "Đang biên dịch llama-cpp-python (Có thể mất 1-2 phút)..."
CMAKE_ARGS="-DGGML_BLAS=ON -DGGML_OPENBLAS=ON" pip install llama-cpp-python --no-cache-dir --force-reinstall --upgrade

# 4. Tải Model GGUF
echo -e "${CYAN}[4/5] Đang tải model Qwen 2.5 1.5B (GGUF)...${NC}"
mkdir -p models

# Dùng script python nhỏ để tải cho tiện (dùng thư viện huggingface_hub vừa cài)
python3 -c "
from huggingface_hub import hf_hub_download
import os

repo_id = 'Qwen/Qwen2.5-1.5B-Instruct-GGUF'
filename = 'qwen2.5-1.5b-instruct-q4_k_m.gguf'
local_dir = './models'

print(f'Đang tải {filename} về {local_dir}...')
path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=local_dir, local_dir_use_symlinks=False)
print(f'Đã tải xong tại: {path}')
"

# 5. Tạo file .env
echo -e "${CYAN}[5/5] Đang cấu hình file .env...${NC}"
if [ ! -f .env ]; then
    cat <<EOT >> .env
# Discord Config
DISCORD_TOKEN=HAY_DIEN_TOKEN_CUA_BAN_VAO_DAY

# LLM Config
LLM_MODEL_PATH=./models/qwen2.5-1.5b-instruct-q4_k_m.gguf
LLM_N_THREADS=2
LLM_CONTEXT_SIZE=4096
EOT
    echo -e "${GREEN}Đã tạo file .env mới.${NC}"
    echo "⚠️  QUAN TRỌNG: Hãy mở file .env và điền DISCORD_TOKEN vào!"
else
    echo "File .env đã tồn tại. Giữ nguyên cấu hình cũ."
fi

echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}   CÀI ĐẶT HOÀN TẤT! SẴN SÀNG CHIẾN ĐẤU      ${NC}"
echo -e "${GREEN}=============================================${NC}"
echo "Để chạy bot, hãy gõ lệnh sau:"
echo -e "${CYAN}source venv/bin/activate${NC}"
echo -e "${CYAN}python main.py${NC}"