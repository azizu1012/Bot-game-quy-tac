# 🕷️ Discord Horror RPG Bot v2.0

Một Discord Bot RPG kinh dí **text-based** với **AI generation**, **chỉ số RPG logic**, và **hệ thống turn-based**. Được thiết kế cho **CPU-only** VPS Linux.

## ✨ Tính Năng Chính

### 🎮 Gameplay
- **Turn-Based Combat** - Mỗi lượt 60 giây, tất cả player phải xác nhận hành động
- **Private Game Channels** - Mỗi game tạo kênh Discord riêng biệt, chỉ player thấy
- **6 Background Classes** - Vận động viên, bác sĩ, cảnh sát, thợ máy, nhà báo, nhà tâm lý
- **RPG Stats System** - HP, Sanity, Agility, Accuracy ảnh hưởng đến kết quả
- **Procedural Maps** - Bản đồ sinh ngẫu nhiên với multiple floors & rooms

### 🤖 AI Integration
- **LLM Scene Descriptions** - Dùng Qwen/LLaMA (CPU) để generate mô tả cảnh động
- **AI Background Profiles** - Tự động generate mô tả cho mỗi background
- **Dynamic Narratives** - Kịch bản được AI tạo dựa trên hành động người chơi
- **Scenario Intro** - AI tạo lời chào bối cảnh mà **không tiết lộ quái vật**

### 💬 Discord UI
- **Interactive Buttons** - Action selection (⚔️ Tấn Công, 🏃 Chạy Trốn, 🔍 Tìm Kiếm, ✅ Xác Nhận)
- **Real-time Dashboard** - Embed hiển thị tình huống, status tất cả player
- **Ephemeral Responses** - Thông báo riêng cho từng người chơi (chỉ họ thấy)
- **100% Tiếng Việt** - Tất cả UI, commands, backgrounds, notifications

### 🗄️ Data Persistence
- **Async SQLite** - Lưu trữ game state, player data, maps
- **Auto-save** - Dữ liệu lưu tự động sau mỗi lượt

## 📦 Cài Đặt

### Yêu Cầu
- **Python**: 3.10+
- **OS**: Linux (VPS), Windows, Mac
- **RAM**: 4GB+ (8GB recommended cho LLM)
- **Disk**: 2GB+ (nếu dùng LLM)

### Quick Start

```bash
# 1. Download repo
cd d:\AI_Projects\Test-super-small-llm

# 2. Cài dependencies
pip install -r horror_bot/requirements.txt

# 3. Tạo file .env
cat > horror_bot/.env << EOF
DISCORD_TOKEN=your_bot_token_here
LLM_MODEL_PATH=path/to/model.gguf
LLM_N_THREADS=4
LLM_CONTEXT_SIZE=4096
EOF

# 4. (Optional) Download LLM model
cd horror_bot && python download_model.py

# 5. Chạy bot
python main.py
```

### File `.env` - Cấu Hình

```env
# Required
DISCORD_TOKEN=your_bot_token_from_discord_dev_portal

# Optional - LLM Configuration
LLM_MODEL_PATH=path/to/qwen-1.7b.gguf
LLM_N_THREADS=4              # CPU threads (4-8 recommended)
LLM_CONTEXT_SIZE=4096        # Context window size
```

## 🎯 Commands

| Command | Mô Tả |
|---------|-------|
| `/newgame [kịch bản]` | Bắt đầu game mới, tạo kênh riêng |
| `/join` | Tham gia game, random background + stats |
| `/endgame` | Kết thúc game & xóa kênh (Admin) |
| `/showdb [table]` | Xem dữ liệu database (Admin) |

## 🎮 Gameplay - Cách Chơi

### Bước 1: Bắt Đầu Game
```
Host: /newgame 🏨 Khách Sạn Bị Nguyền Rủa
```
Bot sẽ:
- ✅ Tạo kênh riêng `🕷️-hotel-game`
- ✅ Add host vào kênh
- ✅ Sinh bản đồ ngẫu nhiên
- ✅ AI generate lời chào bối cảnh

**Lời chào từ AI** (Ví dụ):
> *"Bạn đặt chân vào khách sạn cũ. Không gian im lặm, chỉ có tiếng gió quét qua. Bóng tối bao phủ mọi nơi..."*

### Bước 2: Người Chơi Tham Gia
```
Player: /join
```
Mỗi player nhận được:
- 🎭 **Background ngẫu nhiên** (police, athlete, doctor, journalist, mechanic, psychologist)
- 📊 **Chỉ số riêng** (HP: 85-120, Sanity: 80-130, AGI: 45-70, ACC: 50-70)
- 📋 **Profile embed** hiển thị thông tin của họ
- 🔓 Được add vào private channel

### Bước 3: Mỗi Lượt (60 giây)

1. **Dashboard hiển thị**:
   - 🕷️ Tình huống hiện tại (do AI generate)
   - 👥 Status tất cả player (background, HP, Sanity)
   - ✅/⏳ Indicator xem ai đã confirm action

2. **Player chọn hành động**:
   - ⚔️ **Tấn Công** - Dũa vào bóng tối
   - 🏃 **Chạy Trốn** - Cố gắng thoát
   - 🔍 **Tìm Kiếm** - Khám phá xung quanh

3. **Player xác nhận**:
   - ✅ **XÁC NHẬN** - Confirm hành động của mình

4. **Xử lý Lượt** (khi tất cả confirm hoặc hết giờ):
   - ⚡ Tính toán kết quả dựa trên stats
   - 🤖 AI generate mô tả kết quả
   - 📉 Update HP/Sanity
   - ⏰ Ai không confirm: -15 Sanity penalty
   - 🔄 Bắt đầu lượt mới

### Bước 4: Kết Thúc Game
```
Admin: /endgame
```
Bot sẽ:
- Xóa private channel
- Clear tất cả dữ liệu game

## 📊 Background Classes

| Background | HP | Sanity | AGI | ACC | Đặc Điểm |
|-----------|----|----|--------|-----|----------|
| 🚔 **Cảnh Sát** | 100 | 80 | 50 | **70** | Chính xác cao, dễ tấn công |
| 🏃 **Vận Động Viên** | **110** | 100 | **70** | 50 | Nhanh nhẹn, chạy trốn tốt |
| 🏥 **Bác Sĩ** | 100 | **120** | 50 | 50 | Sanity cao, ổn định |
| 📰 **Nhà Báo** | 85 | 95 | 55 | 65 | Cân bằng, tìm kiếm tốt |
| 🔧 **Thợ Máy** | **120** | 90 | 45 | 55 | HP rất cao, bền bỉ |
| 🧠 **Nhà Tâm Lý** | 90 | **130** | 50 | 60 | Sanity tuyệt vời |

> **Stats Variation**: Chỉ số được random ±15% để tạo đa dạng. Ví dụ: Police có ACC 70±15 → 55-85.

## 🗄️ Database Schema

### `active_games` - Quản Lý Phiên Chơi
```
channel_id (PK)      - ID kênh chính
private_channel_id   - ID kênh riêng cho game
host_id              - ID người tạo game
scenario_type        - Loại kịch bản (hotel/hospital)
current_turn         - Lượt hiện tại
turn_deadline_ts     - Timestamp hết giờ lượt
dashboard_message_id - ID message dashboard
is_active            - Game đang chạy?
```

### `players` - Dữ Liệu Người Chơi
```
user_id (PK)             - ID Discord user
game_id (PK)             - ID game (tham chiếu active_games)
background_id            - ID background (police, doctor, etc)
background_name          - Tên tiếng Việt
background_description   - Mô tả được AI generate
hp                       - Health Points (0-150)
sanity                   - Sanity Points (0-150)
agi                      - Agility/Evasion (10-100)
acc                      - Accuracy/Hit (10-100)
action_this_turn         - Hành động chọn (attack/flee/search)
confirmed_action         - Đã confirm?
has_acted_this_turn      - Đã thực hiện action?
current_location_id      - Vị trí trên map
inventory                - Items (JSON)
```

### `game_maps` - Bản Đồ Game
```
game_id   - Tham chiếu active_games
map_data  - JSON cấu trúc map (nodes, connections, entities)
```

## ⚙️ Customization & Config

### Edit `config.py`
```python
TURN_TIME_SECONDS = 60  # Thay đổi thời gian lượt (default 60s)

DEFAULT_MAP_CONFIG = {
    "hotel": {
        "min_floors": 3,
        "max_floors": 5,
        "min_rooms_per_floor": 5,
        "max_rooms_per_floor": 10
    },
    "hospital": {
        "min_floors": 2,
        "max_floors": 4,
        "min_rooms_per_floor": 8,
        "max_rooms_per_floor": 15
    }
}
```

### Thêm Background Mới (Edit `data/backgrounds.json`)
```json
{
    "id": "engineer",
    "name": "Kỹ Sư",
    "description": "Bạn có kiến thức kỹ thuật sâu sắc.",
    "stats": {
        "hp": 95,
        "sanity": 100,
        "agi": 50,
        "acc": 70
    }
}
```

### Điều Chỉnh LLM (Edit `horror_bot/.env`)
```env
LLM_N_THREADS=8          # Tăng threads cho CPU mạnh hơn
LLM_CONTEXT_SIZE=2048    # Giảm context để LLM chạy nhanh hơn
```

## 🐛 Troubleshooting

| Lỗi | Giải Pháp |
|-----|----------|
| **Bot không tạo kênh** | Cấp quyền `Manage Channels` cho bot |
| **Database locked** | Xóa `horror_bot.db`, bot tạo lại tự động |
| **LLM model not found** | Chạy `python horror_bot/download_model.py` |
| **Slash commands không hiển thị** | Restart Discord client, chờ 5-10 phút, hoặc re-invite bot |
| **Private channel không visible** | Kiểm tra guild role permissions, role settings |
| **LLM quá chậm** | Giảm `LLM_CONTEXT_SIZE` hoặc `LLM_N_THREADS` |
| **Bot timeout khi gọi AI** | Increase timeout trong `game_engine.py`, hoặc dùng model nhỏ hơn |

## 📁 File Structure

```
horror_bot/
├── main.py                      # Entry point, bot setup
├── config.py                    # Game config constants
├── requirements.txt             # Dependencies
├── .env                         # Environment (DISCORD_TOKEN, LLM_PATH)
│
├── cogs/
│   ├── game_commands.py        # /newgame, /join commands + AI intro
│   ├── admin_commands.py       # /endgame, /showdb (Admin)
│   └── game_ui.py              # UI buttons, embeds, PlayerProfileEmbed
│
├── database/
│   ├── db_manager.py           # Async SQLite wrapper
│   └── schema.sql              # DB schema (private_channel, backgrounds)
│
├── services/
│   ├── game_engine.py          # Turn logic, action confirmation, penalties
│   ├── llm_service.py          # LLM integration (Qwen/LLaMA, CPU)
│   ├── map_generator.py        # Procedural map generation
│   ├── background_service.py   # Background randomizer + stats
│   └── scenario_generator.py   # AI scenario/intro generation
│
└── data/
    ├── backgrounds.json        # 6 background classes (tiếng Việt)
    ├── scenarios/
    │   ├── hotel.json
    │   └── hospital.json
    ├── descriptions/           # Pool text cho AI
    │   ├── rooms.txt
    │   └── smells.txt
    └── entities/               # Monster definitions
        ├── ghosts.txt
        └── creatures.txt
```

## 🆕 Gì Mới ở v2.0?

✅ **Private Game Channels** - Mỗi game có kênh Discord riêng biệt  
✅ **Background Randomizer** - 6 classes + chỉ số variation (±15%)  
✅ **AI Scenario Generation** - Mô tả cảnh & lời chào từ AI (không tiết lộ quái vật)  
✅ **Action Confirmation System** - Phải confirm action mới thực hiện  
✅ **100% Tiếng Việt** - Tất cả UI, commands, backgrounds  
✅ **Better Database** - Hỗ trợ private channel, background description, action confirmation  

## 📊 Performance

Trên **Xeon @ 2.8GHz, 16GB RAM**:

| Thao Tác | Thời Gian |
|---------|----------|
| Bot startup | ~5 giây |
| Game creation | ~2 giây |
| Player join | ~3 giây |
| AI LLM response | ~15-45 giây (tuỳ model & context) |
| Turn processing | ~5 giây (không tính AI) |
| Concurrent games | 50+ games (tuỳ RAM) |

## 🚀 Tiếp Theo (Roadmap)

- [ ] Monster encounters & combat mechanics
- [ ] Item loot system & inventory
- [ ] Location navigation (đi lên tầng, vào phòng khác)
- [ ] Skill checks dựa trên stats
- [ ] Persistent character progression
- [ ] Web dashboard & statistics
- [ ] Leaderboard/Hall of Fame
- [ ] Voice channel integration

## 📄 License

MIT - Free to use, modify, redistribute

## 👥 Support

Kiểm tra:
1. Console logs để tìm error messages
2. File `.env` để đảm bảo DISCORD_TOKEN đúng
3. Bot permissions trong Discord server
4. LLM model file tồn tại (nếu offline mode)

---

**Phiên bản**: v2.0 (Private Channels + AI Generation + Action Confirmation)  
**Last Updated**: December 2025  
**Made with ❤️ cho cộng đồng Discord RPG**
