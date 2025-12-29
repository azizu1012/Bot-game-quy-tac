import asyncio
import time
import random
from database import db_manager
from config import TURN_TIME_SECONDS
from services import llm_service

class GameManager:
    """Manages all active game instances and their TurnManagers."""
    def __init__(self):
        self._games = {} # Key: game_id, Value: TurnManager instance

    def get_manager(self, game_id: int, publish_callback=None):
        if game_id not in self._games:
            self._games[game_id] = TurnManager(game_id, self, publish_callback)
        # If manager already exists, update its callback just in case
        elif publish_callback is not None:
             self._games[game_id].publish_callback = publish_callback
        return self._games[game_id]

    def end_game(self, game_id: int):
        if game_id in self._games:
            if self._games[game_id].turn_task:
                self._games[game_id].turn_task.cancel()
            del self._games[game_id]
            print(f"Game {game_id}: Manager cleaned up.")

# Create a global instance of the GameManager
game_manager = GameManager()

class TurnManager:
    def __init__(self, game_id: int, manager: GameManager, publish_callback=None):
        self.game_id = game_id
        self.manager = manager
        self.turn_task = None
        self.processing_lock = asyncio.Lock()  # Thread-safe lock
        self.publish_callback = publish_callback

    async def start_turn(self):
        """Starts the countdown timer for a new turn."""
        await db_manager.execute_query(
            "UPDATE active_games SET current_turn = current_turn + 1, turn_deadline_ts = ? WHERE channel_id = ?",
            (time.time() + TURN_TIME_SECONDS, self.game_id),
            commit=True
        )
        print(f"Game {self.game_id}: Turn started.")

        # Schedule the turn processor to run after the timeout
        if self.turn_task:
            self.turn_task.cancel()
        self.turn_task = asyncio.create_task(self.countdown_and_process)

    async def countdown_and_process(self):
        """Waits for the turn duration and then processes the results."""
        try:
            await asyncio.sleep(TURN_TIME_SECONDS)
            print(f"Game {self.game_id}: Turn time is up. Processing results.")
            await self.process_turn_results(timed_out=True)
        except asyncio.CancelledError:
            print(f"Game {self.game_id}: Turn ended early by all players acting.")
            # The processing will be initiated by the last player's action
            pass

    async def handle_player_action(self, user_id: int, action_type: str):
        """Records a player's action and checks if the turn can end early."""
        # Store the chosen action in the database
        await db_manager.execute_query(
            "UPDATE players SET has_acted_this_turn = 1, action_this_turn = ? WHERE user_id = ? AND game_id = ?",
            (action_type, user_id, self.game_id),
            commit=True
        )
        print(f"Game {self.game_id}: Player {user_id} acted ({action_type}).")

        # Check if all active players have now acted
        all_players = await db_manager.execute_query("SELECT 1 FROM players WHERE game_id = ? AND hp > 0", (self.game_id,), fetchall=True)
        acted_players = await db_manager.execute_query("SELECT 1 FROM players WHERE game_id = ? AND hp > 0 AND has_acted_this_turn = 1", (self.game_id,), fetchall=True)

        if len(acted_players) >= len(all_players):
            if self.turn_task:
                self.turn_task.cancel() # Stop the countdown
            await self.process_turn_results()

    async def process_turn_results(self, timed_out: bool = False):
        """Calculates the outcome of the turn and prepares for the next one."""
        async with self.processing_lock:  # Use lock to prevent race conditions
            print(f"Game {self.game_id}: Processing turn results...")
            turn_events = []

            try:
                # 1. Apply penalty for AFK players if the turn timed out
                if timed_out:
                    afk_players = await db_manager.execute_query(
                        "SELECT user_id, sanity FROM players WHERE game_id = ? AND has_acted_this_turn = 0 AND hp > 0",
                        (self.game_id,), fetchall=True
                    )
                    penalty_sanity = 10
                    for player_row in afk_players:
                        await db_manager.execute_query(
                            "UPDATE players SET sanity = sanity - ? WHERE user_id = ? AND game_id = ?",
                            (penalty_sanity, player_row['user_id'], self.game_id), commit=True
                        )
                        turn_events.append(f"<@{player_row['user_id']}> was slow to react and lost {penalty_sanity} sanity!")

                # 2. Process actions (this is a simplified example)
                # In a real game, you'd have monster AI, check locations, etc.
                actions = await db_manager.execute_query(
                    "SELECT user_id, action_this_turn FROM players WHERE game_id = ? AND has_acted_this_turn = 1",
                    (self.game_id,), fetchall=True
                )
                for action in actions:
                    if action['action_this_turn'] == 'search':
                        turn_events.append(f"<@{action['user_id']}> found a dusty old coin.")
                    elif action['action_this_turn'] == 'attack':
                        turn_events.append(f"<@{action['user_id']}> swung wildly at the darkness.")
                
                # 3. Use LLM to generate a narrative summary of the turn
                scene_keywords = ["darkness", "fear"] + [a['action_this_turn'] for a in actions if a['action_this_turn']]
                summary = await asyncio.wait_for(
                    llm_service.describe_scene(list(set(scene_keywords))),
                    timeout=5.0  # 5 second timeout for LLM
                )
                
                # 4. Reset player turn status for the next round
                await db_manager.execute_query(
                    "UPDATE players SET has_acted_this_turn = 0, action_this_turn = NULL WHERE game_id = ?",
                    (self.game_id,), commit=True
                )
                
                print(f"Game {self.game_id}: Turn processed. Summary: {summary}")
                
                # 5. Publish results via callback if it exists
                if self.publish_callback:
                    try:
                        await self.publish_callback(self.game_id, summary, turn_events)
                    except Exception as e:
                        print(f"Game {self.game_id}: Error in publish_callback: {e}")
                
                # 6. Start the next turn
                await self.start_turn()
            except asyncio.TimeoutError:
                print(f"Game {self.game_id}: LLM timeout, skipping description")
                await self.start_turn()
            except Exception as e:
                print(f"Game {self.game_id}: Error processing turn: {e}")
                await self.start_turn()


# --- RPG Calculation Functions ---
def calculate_hit(player_acc: int, monster_evasion: int) -> bool:
    hit_chance = min(max((player_acc - monster_evasion) / 100.0, 0.1), 0.95)
    return random.random() < hit_chance

def calculate_flee(player_agi: int) -> bool:
    flee_chance = min(max(player_agi / 100.0, 0.1), 0.9)
    return random.random() < flee_chance

# --- Global Accessor ---
async def register_action(user_id: int, game_id: int, action: str):
    """Entry point for the UI to register a player's action."""
    manager = game_manager.get_manager(game_id)
    await manager.handle_player_action(user_id, action)