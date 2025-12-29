import json
import random
import uuid

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

    def connect_nodes(self, from_node_id: str, to_node_id: str, direction: str):
        """Creates a two-way connection between nodes."""
        if from_node_id in self.nodes and to_node_id in self.nodes:
            # Simple connection for now, can be expanded (e.g., one-way doors)
            opposite_direction = {"north": "south", "south": "north", "east": "west", "west": "east"}[direction]
            self.nodes[from_node_id].connections[direction] = to_node_id
            self.nodes[to_node_id].connections[opposite_direction] = from_node_id

def generate_map_structure(scenario_path: str) -> MapStructure:
    """
    Generates a random map structure based on a scenario JSON file,
    creating a grid-like layout for each floor.
    """
    try:
        with open(scenario_path, 'r') as f:
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

        # Connect this floor to the previous one
        if previous_floor_stair_down:
            stair_up_node = random.choice(floor_nodes)
            map_structure.connect_nodes(previous_floor_stair_down.id, stair_up_node.id, "down")
            stair_up_node.room_type = "stairwell_down" # This room now leads down

        # Create a stairwell leading to the *next* floor
        if floor_num < num_floors - 1:
            stair_down_node = random.choice(floor_nodes)
            # Ensure the chosen stairwell node is not the same as the entry stairwell, if possible
            if len(floor_nodes) > 1 and 'stair_up_node' in locals() and stair_down_node == stair_up_node:
                stair_down_node = random.choice([n for n in floor_nodes if n != stair_up_node])
            
            stair_down_node.room_type = "stairwell_up" # This room leads up
            previous_floor_stair_down = stair_down_node
            
    # Add some entities/events (example)
    for node in map_structure.nodes.values():
        if random.random() < 0.2: # 20% chance to have an entity
            node.entities.append("creature")
        if random.random() < 0.1: # 10% chance to have an event
            node.events.append("locked_chest")
            
    return map_structure

if __name__ == '__main__':
    # Example usage:
    # Ensure you run this from the root of the horror_bot project
    # or adjust the path accordingly.
    import os
    # Fix path for direct execution
    if os.getcwd().endswith('services'):
        os.chdir('..')
        
    hotel_map = generate_map_structure("data/scenarios/hotel.json")
    if hotel_map:
        print(f"Generated map for '{hotel_map.scenario_name}' with {len(hotel_map.nodes)} rooms.")
        print(f"Starting node: {hotel_map.start_node_id}")
        # You can inspect the first node's connections
        start_node = hotel_map.nodes[hotel_map.start_node_id]
        print(f"Start node connections: {start_node.connections}")
