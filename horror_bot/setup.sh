#!/bin/bash

# Dừng script ngay nếu có lỗi xảy ra
set -e

# Màu sắc cho dễ nhìn
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== BẮT ĐẦU CÀI ĐẶT AUTOMATION CHO BOT GAME KINH DỊ ===${NC}"

# 1. Cài đặt thư viện hệ thống (Đã thêm pkg-config để sửa lỗi mới nhất)
echo -e "${CYAN}[1/5] Đang cập nhật hệ thống và cài build tools...${NC}"
if [ "$EUID" -ne 0 ]; then 
  echo "Cần quyền root để cài gói hệ thống. Vui lòng nhập mật khẩu:"
  # ĐÃ SỬA: Thêm pkg-config và libopenblas-dev
  sudo apt-get update && sudo apt-get install -y python3-venv python3-dev build-essential libopenblas-dev pkg-config
else
  # ĐÃ SỬA: Thêm pkg-config và libopenblas-dev
  apt-get update && apt-get install -y python3-venv python3-dev build-essential libopenblas-dev pkg-config
fi

# 2. Tạo môi trường ảo Python
echo -e "${CYAN}[2/5] Đang tạo môi trường ảo (venv)...${NC}"
if [ -d "venv" ]; then
    echo "Thư mục venv đã tồn tại."
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

# Dùng script python nhỏ để tải cho tiện
python3 -c "
from huggingface_hub import hf_hub_download
import os

repo_id = 'Qwen/Qwen2.5-1.5B-Instruct-GGUF'
filename = 'qwen2.5-1.5b-instruct-q4_k_m.gguf'
local_dir = './models'

# Kiểm tra nếu file chưa tồn tại thì mới tải
full_path = os.path.join(local_dir, filename)
if not os.path.exists(full_path):
    print(f'Đang tải {filename} về {local_dir}...')
    path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=local_dir, local_dir_use_symlinks=False)
    print(f'Đã tải xong tại: {path}')
else:
    print('Model đã tồn tại, bỏ qua bước tải.')
"

# 5. Tạo file .env nếu chưa có
echo -e "${CYAN}[5/5] Đang kiểm tra file .env...${NC}"
if [ ! -f .env ]; then
    cat <<EOT >> .env
# Discord Config
DISCORD_TOKEN=HAY_DIEN_TOKEN_CUA_BAN_VAO_DAY

# LLM Config
LLM_MODEL_PATH=./models/qwen2.5-1.5b-instruct-q4_k_m.gguf
LLM_N_THREADS=2
LLM_CONTEXT_SIZE=4096
EOT
    echo -e "${GREEN}Đã tạo file .env mẫu.${NC}"
    echo "⚠️  QUAN TRỌNG: Hãy mở file .env và điền Token Discord vào!"
else
    echo "File .env đã tồn tại. Giữ nguyên."
fi

echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}   CÀI ĐẶT HOÀN TẤT! SẴN SÀNG CHIẾN ĐẤU      ${NC}"
echo -e "${GREEN}=============================================${NC}"