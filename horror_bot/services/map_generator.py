import json
import random
import uuid
import os

class MapNode:
    """Represents a single location (room) on the map."""
    def __init__(self, room_type: str, description: str = "An unremarkable space."):
        self.id = str(uuid.uuid4())
        self.room_type = room_type
        self.description = description
        self.connections = {}  # e.g., {"north": "node_id_123"}
        self.entities = []  # Monsters or NPCs in the room
        self.events = []    # Special events or items

    def __repr__(self):
        return f"MapNode(id={self.id}, type={self.room_type})"

    def to_dict(self):
        """Convert MapNode to a dictionary for JSON serialization."""
        return {
            "id": self.id,
            "room_type": self.room_type,
            "description": self.description,
            "connections": self.connections,
            "entities": self.entities,
            "events": self.events
        }

class MapStructure:
    """Represents the entire game map as a graph of nodes."""
    def __init__(self, scenario_name: str):
        self.scenario_name = scenario_name
        self.nodes = {}  # A flat dictionary of all nodes by their ID
        self.start_node_id = None

    def add_node(self, node: MapNode):
        """Adds a node to the map."""
        self.nodes[node.id] = node
        if not self.start_node_id:
            self.start_node_id = node.id

    def to_dict(self):
        """Convert entire map structure to a serializable dictionary."""
        return {
            "scenario_name": self.scenario_name,
            "start_node_id": self.start_node_id,
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()}
        }

    def connect_nodes(self, from_node_id: str, to_node_id: str, direction: str):
        """Creates a two-way connection between nodes."""
        if from_node_id in self.nodes and to_node_id in self.nodes:
            # FIX 1: Thêm cặp hướng up/down vào đây để không bị KeyError
            opposites = {
                "north": "south", 
                "south": "north", 
                "east": "west", 
                "west": "east",
                "up": "down",       # <-- Đã thêm
                "down": "up"        # <-- Đã thêm
            }
            
            if direction not in opposites:
                print(f"Warning: Unknown direction '{direction}'")
                return

            opposite_direction = opposites[direction]
            self.nodes[from_node_id].connections[direction] = to_node_id
            self.nodes[to_node_id].connections[opposite_direction] = from_node_id

def generate_map_structure(scenario_path: str) -> MapStructure:
    """
    Generates a random map structure based on a scenario JSON file,
    creating a grid-like layout for each floor.
    """
    # Xử lý đường dẫn file an toàn hơn
    if not os.path.exists(scenario_path):
        # Thử tìm trong thư mục gốc nếu đường dẫn tương đối bị sai
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scenario_path = os.path.join(base_dir, scenario_path)

    try:
        with open(scenario_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Scenario file not found at {scenario_path}")
        return None

    map_structure = MapStructure(scenario_name=config.get("name", "Unknown Scenario"))
    num_floors = random.randint(config.get("min_floors", 1), config.get("max_floors", 1))
    
    previous_floor_stair_down = None

    for floor_num in range(num_floors):
        # Determine grid size, e.g., 3x3, 4x3, etc.
        grid_w = random.randint(3, 5)
        grid_h = random.randint(2, 4)
        floor_grid = [[None for _ in range(grid_w)] for _ in range(grid_h)]
        
        # Create nodes for the grid
        for y in range(grid_h):
            for x in range(grid_w):
                # Have a chance for a room to not exist, creating holes in the map
                if random.random() < 0.8:
                    node = MapNode(room_type="room", description=f"A room on floor {floor_num+1}")
                    map_structure.add_node(node)
                    floor_grid[y][x] = node

        # Connect nodes in the grid
        for y in range(grid_h):
            for x in range(grid_w):
                current_node = floor_grid[y][x]
                if not current_node:
                    continue
                
                # Connect to North neighbor
                if y > 0 and floor_grid[y-1][x]:
                    map_structure.connect_nodes(current_node.id, floor_grid[y-1][x].id, "north")
                # Connect to West neighbor
                if x > 0 and floor_grid[y][x-1]:
                    map_structure.connect_nodes(current_node.id, floor_grid[y][x-1].id, "west")

        # Get a list of all actual nodes on this floor
        floor_nodes = [node for row in floor_grid for node in row if node]
        if not floor_nodes:
             continue # Skip empty floors

        # Connect this floor to the previous one (UP STAIRS)
        if previous_floor_stair_down:
            stair_up_node = random.choice(floor_nodes)
            # Nối từ tầng trên (previous) đi xuống (down) tầng này (stair_up_node)
            map_structure.connect_nodes(previous_floor_stair_down.id, stair_up_node.id, "down")
            
            # FIX 2: Phòng này dẫn lên tầng trên, nên gọi là stairwell_up
            stair_up_node.room_type = "stairwell_up" 
            stair_up_node.description += " (Stairs going UP)"

        # Create a stairwell leading to the *next* floor (DOWN STAIRS)
        if floor_num < num_floors - 1:
            stair_down_node = random.choice(floor_nodes)
            # Ensure the chosen stairwell node is not the same as the entry stairwell, if possible
            if len(floor_nodes) > 1 and 'stair_up_node' in locals() and stair_down_node == stair_up_node:
                stair_down_node = random.choice([n for n in floor_nodes if n != stair_up_node])
            
            # FIX 3: Phòng này dẫn xuống tầng dưới, nên gọi là stairwell_down
            stair_down_node.room_type = "stairwell_down"
            stair_down_node.description += " (Stairs going DOWN)"
            
            # Lưu lại node này để vòng lặp sau nối vào
            previous_floor_stair_down = stair_down_node
            
    # Add some entities/events (example)
    for node in map_structure.nodes.values():
        if random.random() < 0.2: # 20% chance to have an entity
            node.entities.append("creature")
        if random.random() < 0.1: # 10% chance to have an event
            node.events.append("locked_chest")
            
    return map_structure