-- Bảng quản lý phiên chơi
CREATE TABLE IF NOT EXISTS active_games (
    channel_id INTEGER PRIMARY KEY,
    lobby_channel_id INTEGER,        -- Kênh sảnh chính (#game-lobby)
    dashboard_channel_id INTEGER,    -- Kênh bảng chỉ số (#game-dashboard) READ-ONLY
    dashboard_message_id INTEGER,    -- Message ID để update stats real-time
    host_id INTEGER,                 -- Game creator
    game_creator_id INTEGER,         -- Người tạo game
    scenario_type TEXT,
    game_code TEXT,                  -- Mã phòng unique
    is_active BOOLEAN DEFAULT 1,
    setup_by_admin_id INTEGER,       -- Admin người setup
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng setup config (Admin quản lý)
CREATE TABLE IF NOT EXISTS game_setups (
    setup_id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    category_id INTEGER,             -- Category để tạo game channels
    created_by INTEGER,              -- Admin tạo setup này
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng lưu Map (JSON)
CREATE TABLE IF NOT EXISTS game_maps (
    game_id INTEGER,
    map_data JSON,                   -- Cấu trúc cây node
    FOREIGN KEY(game_id) REFERENCES active_games(channel_id)
);

-- Bảng người chơi & Chỉ số
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER,
    game_id INTEGER,
    
    -- Kênh riêng tư của player
    private_channel_id INTEGER,      -- Kênh #private-[player-name]
    
    -- Chỉ số cơ bản
    hp INTEGER DEFAULT 100,
    sanity INTEGER DEFAULT 100,
    
    -- Chỉ số RPG & Background
    agi INTEGER DEFAULT 50,          -- Agility (Tốc độ/Chạy trốn)
    acc INTEGER DEFAULT 50,          -- Accuracy (Chính xác)
    background_id TEXT,              -- ID nghề nghiệp
    background_name TEXT,            -- Tên nghề nghiệp tiếng Việt
    background_description TEXT,     -- Mô tả về nghề nghiệp
    
    -- Vị trí và trạng thái
    current_location_id TEXT,        -- Room ID hiện tại trên map
    location_name TEXT,              -- Tên room (cached)
    inventory JSON DEFAULT '[]',     -- Danh sách vật phẩm
    
    -- LLM Context Memory (per-player)
    llm_conversation_history JSON DEFAULT '[]', -- Lịch sử chat với LLM [{"role": "user", "content": "..."}, ...]
    last_action_result TEXT,         -- Kết quả hành động cuối cùng
    
    -- Trạng thái play
    is_ready BOOLEAN DEFAULT 0,      -- Đã start game chưa
    discovered_hidden_rules JSON DEFAULT '[]', -- Rules mà player đã phát hiện
    
    PRIMARY KEY(user_id, game_id)
);

-- Bảng lưu Rules cho mỗi game (10 public + 10 hidden)
CREATE TABLE IF NOT EXISTS game_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER,
    rule_text TEXT,
    is_public BOOLEAN DEFAULT 1,     -- 1=Public, 0=Hidden
    rule_type TEXT DEFAULT 'lore',   -- 'lore', 'mechanic', 'clue', 'warning'
    discovery_requirement TEXT,      -- Cách tìm được rule
    FOREIGN KEY(game_id) REFERENCES active_games(channel_id)
);

-- Bảng lưu Context về Scenario
CREATE TABLE IF NOT EXISTS game_context (
    context_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER,
    scenario_type TEXT,
    current_threat_level INTEGER DEFAULT 0, -- 0=Safe, 1=Danger, 2=Critical
    active_dangers JSON DEFAULT '[]', -- Array các nguy hiểm
    recent_events JSON DEFAULT '[]', -- Lịch sử sự kiện
    global_log TEXT,                 -- Log các sự kiện chung (hiển thị ở lobby)
    FOREIGN KEY(game_id) REFERENCES active_games(channel_id)
);

-- Bảng lưu encounter (khi 2+ player gặp nhau)
CREATE TABLE IF NOT EXISTS player_encounters (
    encounter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER,
    location_id TEXT,                -- Room ID nơi gặp
    player_ids JSON,                 -- Array user_id của players ở đây
    encounter_text TEXT,             -- Mô tả encounter được gen bởi LLM
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(game_id) REFERENCES active_games(channel_id)
);
