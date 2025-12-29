# Game settings
TURN_TIME_SECONDS = 60
THINKING_PHASE_SECONDS = 30  # Time for players to discuss before next turn

# Map generation settings
DEFAULT_MAP_CONFIG = {
    "asylum": {
        "min_floors": 4,
        "max_floors": 6,
        "min_rooms_per_floor": 5,
        "max_rooms_per_floor": 10
    },
    "factory": {
        "min_floors": 5,
        "max_floors": 7,
        "min_rooms_per_floor": 6,
        "max_rooms_per_floor": 12
    },
    "ghost_village": {
        "min_floors": 1,
        "max_floors": 3,
        "min_rooms_per_floor": 8,
        "max_rooms_per_floor": 15
    },
    "cursed_mansion": {
        "min_floors": 6,
        "max_floors": 9,
        "min_rooms_per_floor": 4,
        "max_rooms_per_floor": 8
    },
    "mine": {
        "min_floors": 7,
        "max_floors": 12,
        "min_rooms_per_floor": 3,
        "max_rooms_per_floor": 7
    },
    "prison": {
        "min_floors": 4,
        "max_floors": 6,
        "min_rooms_per_floor": 8,
        "max_rooms_per_floor": 15
    },
    "abyss": {
        "min_floors": 10,
        "max_floors": 15,
        "min_rooms_per_floor": 2,
        "max_rooms_per_floor": 5
    },
    "dead_forest": {
        "min_floors": 1,
        "max_floors": 3,
        "min_rooms_per_floor": 10,
        "max_rooms_per_floor": 20
    },
    "research_hospital": {
        "min_floors": 5,
        "max_floors": 8,
        "min_rooms_per_floor": 6,
        "max_rooms_per_floor": 12
    },
    "ghost_ship": {
        "min_floors": 6,
        "max_floors": 10,
        "min_rooms_per_floor": 4,
        "max_rooms_per_floor": 8
    }
}

# Player default stats
DEFAULT_PLAYER_STATS = {
    "hp": 100,
    "sanity": 100,
    "agi": 50,
    "acc": 50
}
