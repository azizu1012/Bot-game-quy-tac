-- Bảng quản lý phiên chơi
CREATE TABLE IF NOT EXISTS active_games (
    channel_id INTEGER PRIMARY KEY,
    private_channel_id INTEGER,  -- Kênh riêng cho trò chơi này
    host_id INTEGER,
    scenario_type TEXT,
    current_turn INTEGER DEFAULT 0,
    turn_deadline_ts REAL, -- Timestamp thời điểm hết giờ
    is_active BOOLEAN DEFAULT 1,
    dashboard_message_id INTEGER
);

-- Bảng lưu Map (JSON)
CREATE TABLE IF NOT EXISTS game_maps (
    game_id INTEGER,
    map_data JSON, -- Cấu trúc cây node
    FOREIGN KEY(game_id) REFERENCES active_games(channel_id)
);

-- Bảng người chơi & Chỉ số
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER,
    game_id INTEGER,
    
    -- Chỉ số cơ bản
    hp INTEGER DEFAULT 100,
    sanity INTEGER DEFAULT 100,
    
    -- Chỉ số RPG & Background
    agi INTEGER DEFAULT 50, -- Agility (Tốc độ/Chạy trốn)
    acc INTEGER DEFAULT 50, -- Accuracy (Chính xác)
    background_id TEXT,     -- ID nghề nghiệp (police, doctor...)
    background_name TEXT,   -- Tên nghề nghiệp tiếng Việt
    background_description TEXT, -- Mô tả về nghề nghiệp
    
    -- Trạng thái lượt
    has_acted_this_turn BOOLEAN DEFAULT 0, -- Check để xử lý Timeout
    action_this_turn TEXT,                 -- The action taken (e.g., 'attack', 'flee')
    confirmed_action BOOLEAN DEFAULT 0,    -- Đã confirm action chưa
    
    current_location_id TEXT,
    inventory JSON,
    PRIMARY KEY(user_id, game_id)
);
