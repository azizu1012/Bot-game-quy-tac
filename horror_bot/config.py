# Game settings
TURN_TIME_SECONDS = 60

# Map generation settings
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

# Player default stats
DEFAULT_PLAYER_STATS = {
    "hp": 100,
    "sanity": 100,
    "agi": 50,
    "acc": 50
}
