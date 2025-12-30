#!/bin/bash
set -e

# Màu sắc
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${GREEN}=== BẮT ĐẦU CÀI ĐẶT LẠI (SẠCH) ===${NC}"

# 1. Cài đặt thư viện hệ thống (Đã thêm pkg-config để fix lỗi build)
echo -e "${CYAN}[1/5] Cài đặt build tools...${NC}"
if [ "$EUID" -ne 0 ]; then 
  sudo apt-get update && sudo apt-get install -y python3-venv python3-dev build-essential libopenblas-dev pkg-config
else
  apt-get update && apt-get install -y python3-venv python3-dev build-essential libopenblas-dev pkg-config
fi

# 2. Tạo venv
echo -e "${CYAN}[2/5] Tạo môi trường ảo...${NC}"
rm -rf venv # Xóa venv cũ nếu có cho chắc
python3 -m venv venv
source venv/bin/activate

# 3. Cài thư viện Python
echo -e "${CYAN}[3/5] Cài dependencies...${NC}"
pip install --upgrade pip
pip install discord.py python-dotenv huggingface-hub aiosqlite

# Cài llama-cpp-python (Build với OpenBLAS)
echo "Đang biên dịch llama-cpp-python..."
CMAKE_ARGS="-DGGML_BLAS=ON -DGGML_OPENBLAS=ON" pip install llama-cpp-python --no-cache-dir --force-reinstall --upgrade

# 4. Kiểm tra Model (Code này sẽ bỏ qua tải nếu thấy file trong thư mục models)
echo -e "${CYAN}[4/5] Kiểm tra Model...${NC}"
mkdir -p models
python3 -c "
import os
from huggingface_hub import hf_hub_download

filename = 'qwen2.5-1.5b-instruct-q4_k_m.gguf'
local_dir = './models'
full_path = os.path.join(local_dir, filename)

if os.path.exists(full_path):
    print(f'✅ Tìm thấy model tại {full_path}. Bỏ qua tải xuống.')
else:
    print(f'⚡ Không thấy model, đang tải mới...')
    hf_hub_download(repo_id='Qwen/Qwen2.5-1.5B-Instruct-GGUF', filename=filename, local_dir=local_dir)
"

# 5. Tạo .env
echo -e "${CYAN}[5/5] Kiểm tra file .env...${NC}"
if [ ! -f .env ]; then
    echo "Tạo file .env mới..."
    cat <<EOT >> .env
# Discord Config
DISCORD_TOKEN=HAY_DIEN_TOKEN_CUA_BAN_VAO_DAY
ADMIN_ID=YOUR_DISCORD_USER_ID_HERE

# LLM Config
LLM_MODEL_PATH=./models/qwen2.5-1.5b-instruct-q4_k_m.gguf
LLM_N_THREADS=4
LLM_CONTEXT_SIZE=8192
EOT
    echo -e "${GREEN}⚠️  Đã tạo file .env mới. HÃY ĐIỀN TOKEN VÀ ADMIN_ID VÀO!${NC}"
else
    echo "File .env đã tồn tại."
fi

echo -e "${GREEN}=== CÀI ĐẶT HOÀN TẤT ===${NC}"