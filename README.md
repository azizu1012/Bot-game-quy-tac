# 🎮 Horror Bot - Discord RPG Game Master

Một Discord Bot quản trò (Game Master) cho game kinh dị text-based, kết hợp thuật toán RNG và AI (Qwen3-1.7B) để mô tả lại cảnh kịch động.

## 🌟 Tính năng

- **AI-Powered Descriptions**: Dùng Qwen3 LLM để sinh description động cho mỗi cảnh
- **Turn-Based Combat**: Quản lý lượt chơi với countdown timer
- **RPG Stats System**: HP, Sanity, Agility, Accuracy ảnh hưởng đến kết quả
- **Procedural Maps**: Sinh ngẫu nhiên cấu trúc tầng/phòng dựa trên config
- **Discord UI**: Embed dashboard + Buttons để interaction
- **Async Database**: SQLite async cho quản lý state
- **Dynamic Model Loading**: Dễ dàng thay đổi hoặc cập nhật model

## 📁 Cấu trúc Project

```
horror_bot/
├── main.py                 # Entry point, khởi tạo bot
├── config.py              # Cấu hình game settings
├── .env                   # Environment variables (Discord token, model path)
├── requirements.txt       # Python dependencies
├── data/
│   ├── backgrounds.json        # Định nghĩa nhân vật class
│   ├── scenarios/              # Config map (hotel.json, hospital.json)
│   ├── descriptions/           # Pool text cho AI (rooms.txt, smells.txt)
│   └── entities/               # Quái vật (ghosts.txt, creatures.txt)
├── database/
│   ├── db_manager.py      # Async SQLite connection
│   └── schema.sql         # Database schema
├── services/
│   ├── llm_service.py     # AI Wrapper (Qwen3, dynamic model loading)
│   ├── game_engine.py     # Core logic: Turn, Stats, Penalty
│   └── map_generator.py   # Sinh map structure
└── cogs/
    ├── game_commands.py   # Slash commands: /newgame, /join
    ├── game_ui.py         # Discord Embed & Button UI
    └── admin_commands.py  # Debug commands
```

## 🚀 Quick Start

### 1. Cài dependencies
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac: source venv/bin/activate
pip install -r horror_bot/requirements.txt
```

### 2. Tải model
```bash
python download_model.py
```
Điều này sẽ tải Qwen3-1.7B (~3.2GB) vào `horror_bot/models/`

### 3. Cấu hình Discord Token
```bash
# Edit horror_bot/.env
DISCORD_TOKEN="your-bot-token-here"
```

### 4. Chạy bot
```bash
cd horror_bot
python main.py
```

## 🤖 LLM Configuration

### File: `horror_bot/.env`

```env
# LLM Model (có thể thay đổi)
LLM_MODEL_NAME="Qwen/Qwen3-1.7B-Instruct"
LLM_MODEL_PATH="./models/Qwen3-1.7B-Instruct"

# Device (cpu/cuda)
LLM_DEVICE="cpu"

# Data type (float32/float16/bfloat16/int8)
LLM_DTYPE="float32"
```

### Model được hỗ trợ (HuggingFace)

- **Qwen3-1.7B** (default) - Nhỏ, nhanh, tốt cho CPU
- **Mistral-7B-Instruct** - Cân bằng quality & speed
- **LLama-2-7B** - Open-source, mạnh hơn Qwen nhưng chậm

### Dynamic Model Loading

Code tự động:
1. Kiểm tra nếu model tồn tại locally → Load từ `./models/`
2. Nếu không tồn tại → Download từ HuggingFace
3. Support cả CPU và GPU (auto-detect)

## 📖 Game Flow

### Khởi tạo game
```
/newgame [scenario: hotel|hospital]
```

### Join game
```
/join
```

### Main Loop
1. **Start Turn** → Bot tạo embed dashboard
2. **Player Actions** → Players bấm buttons (Attack/Flee/Search)
3. **AI Description** → LLM sinh scene description
4. **Resolve Effects** → Tính toán damage, sanity loss, vv
5. **Next Turn** → Quay lại bước 1

## ⚙️ Deployment

Xem [DEPLOYMENT.md](DEPLOYMENT.md) để:
- Hướng dẫn cài đặt trên Linux VPS
- Auto-start với systemd
- Troubleshooting
- Performance tuning

### Quick deploy command
```bash
# Linux
bash setup_and_run.sh

# Windows
setup_and_run.bat
```

## 🔧 Customization

### Thay đổi scenario map
Edit `data/scenarios/hotel.json`:
```json
{
  "min_floors": 3,
  "max_floors": 5,
  "min_rooms_per_floor": 5,
  "max_rooms_per_floor": 10
}
```

### Thêm descriptions
Thêm dòng vào `data/descriptions/rooms.txt`, `smells.txt`, vv
Mỗi dòng là một description option cho AI sử dụng.

### Thay đổi player stats
Edit `config.py`:
```python
DEFAULT_PLAYER_STATS = {
    "hp": 100,
    "sanity": 100,
    "agi": 50,
    "acc": 50
}
```

## 📊 System Requirements

- **OS**: Linux/Windows/Mac
- **Python**: 3.10+
- **RAM**: 8GB+ (16GB+ recommended)
- **Disk**: 5GB+ (cho model)
- **CPU**: Xeon/i7/Ryzen hoặc tương đương

### Thời gian response (Qwen3-1.7B)
- **GPU (NVIDIA)**: ~2-5 seconds
- **CPU (Xeon)**: ~20-45 seconds
- **CPU (i7)**: ~30-60 seconds

## 📝 Project Status

- [x] Bot structure & cogs setup
- [x] LLM integration (Qwen3)
- [x] Dynamic model loading
- [ ] Game engine logic (TBD)
- [ ] UI buttons & embeds (TBD)
- [ ] Database schema & async support (TBD)
- [ ] Map generator (TBD)

## 🐛 Troubleshooting

### Model load error
```
Error: No space left on device
```
→ Check disk space: `df -h` (cần 5GB+)

### Bot không connect Discord
→ Kiểm tra `DISCORD_TOKEN` trong `.env`

### Model quá chậm
→ Giảm `max_new_tokens` trong `llm_service.py`  
→ Sử dụng `int8` quantization: `LLM_DTYPE="int8"`

## 📚 Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Server deployment guide
- [config.py](horror_bot/config.py) - Game settings
- [llm_service.py](horror_bot/services/llm_service.py) - LLM API
- [download_model.py](download_model.py) - Model download script

## 📞 Support

1. Check console logs cho error messages
2. Verify `.env` variables
3. Test LLM loading: `python -c "from horror_bot.services.llm_service import load_llm; load_llm()"`

## 📄 License

MIT
