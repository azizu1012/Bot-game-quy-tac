import asyncio
import time
import random
from database import db_manager
from config import TURN_TIME_SECONDS, THINKING_PHASE_SECONDS
from services import llm_service, scenario_generator

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
        self.thinking_task = None
        self.processing_lock = asyncio.Lock()  # Thread-safe lock
        self.publish_callback = publish_callback
        self.action_counts = {}  # Track action confirmations per action type
        self.phase = "action"  # "action" or "thinking"

    async def start_turn(self):
        """Starts the countdown timer for a new turn."""
        await db_manager.execute_query(
            "UPDATE active_games SET current_turn = current_turn + 1, turn_deadline_ts = ? WHERE channel_id = ?",
            (time.time() + TURN_TIME_SECONDS, self.game_id),
            commit=True
        )
        # Reset actions để turn mới
        self.action_counts = {}
        self.phase = "action"
        print(f"Game {self.game_id}: Turn started. Phase: action")

        # Schedule the turn processor to run after the timeout
        if self.turn_task:
            self.turn_task.cancel()
        self.turn_task = asyncio.create_task(self.countdown_and_process())

    async def countdown_and_process(self):
        """Waits for the turn duration and then processes the results."""
        try:
            await asyncio.sleep(TURN_TIME_SECONDS)
            print(f"Game {self.game_id}: Turn time is up. Processing results.")
            await self.process_turn_results(timed_out=True)
        except asyncio.CancelledError:
            print(f"Game {self.game_id}: Turn ended early by all players acting.")
            pass

    async def start_thinking_phase(self, duration: int = None):
        """Starts the thinking/discussion phase before next turn."""
        if duration is None:
            duration = THINKING_PHASE_SECONDS
        self.phase = "thinking"
        print(f"Game {self.game_id}: Thinking phase started ({duration}s).")
        
        if self.thinking_task:
            self.thinking_task.cancel()
        self.thinking_task = asyncio.create_task(self.thinking_countdown(duration))

    async def thinking_countdown(self, duration: int):
        """Waits for thinking phase and then auto-starts next turn."""
        try:
            await asyncio.sleep(duration)
            print(f"Game {self.game_id}: Thinking phase ended. Auto-starting next turn.")
            # Publish "continuing" message then start turn
            if self.publish_callback:
                try:
                    await self.publish_callback(self.game_id, "🎮 **LƯỢT MỚI BẮT ĐẦU!**", [])
                except Exception as e:
                    print(f"Game {self.game_id}: Error in thinking phase callback: {e}")
            await self.start_turn()
        except asyncio.CancelledError:
            print(f"Game {self.game_id}: Thinking phase cancelled.")
            pass

    async def handle_player_action(self, user_id: int, action_type: str):
        """Records a player's action - first selection chưa confirm."""
        # Store the chosen action in the database
        await db_manager.execute_query(
            "UPDATE players SET action_this_turn = ?, confirmed_action = 0 WHERE user_id = ? AND game_id = ?",
            (action_type, user_id, self.game_id),
            commit=True
        )
        print(f"Game {self.game_id}: Player {user_id} selected action ({action_type}), awaiting confirmation.")

    async def confirm_action(self, user_id: int):
        """Người chơi confirm lựa chọn hành động của họ."""
        player = await db_manager.execute_query(
            "SELECT action_this_turn FROM players WHERE user_id = ? AND game_id = ?",
            (user_id, self.game_id), fetchone=True
        )
        
        if not player or not player['action_this_turn']:
            return False
        
        # Mark as confirmed
        await db_manager.execute_query(
            "UPDATE players SET confirmed_action = 1, has_acted_this_turn = 1 WHERE user_id = ? AND game_id = ?",
            (user_id, self.game_id),
            commit=True
        )
        print(f"Game {self.game_id}: Player {user_id} confirmed action.")

        # Check if all active players have confirmed
        all_players = await db_manager.execute_query(
            "SELECT 1 FROM players WHERE game_id = ? AND hp > 0", 
            (self.game_id,), fetchall=True
        )
        confirmed_players = await db_manager.execute_query(
            "SELECT 1 FROM players WHERE game_id = ? AND hp > 0 AND confirmed_action = 1", 
            (self.game_id,), fetchall=True
        )

        if len(confirmed_players) >= len(all_players):
            if self.turn_task:
                self.turn_task.cancel()
            await self.process_turn_results()
        
        return True

    async def process_turn_results(self, timed_out: bool = False):
        """Calculates the outcome of the turn and prepares for the next one."""
        async with self.processing_lock:
            print(f"Game {self.game_id}: Processing turn results...")
            turn_events = []

            try:
                game_info = await db_manager.execute_query(
                    "SELECT scenario_type FROM active_games WHERE channel_id = ?",
                    (self.game_id,), fetchone=True
                )
                scenario_type = game_info['scenario_type'] if game_info else 'hotel'

                # 1. Apply penalty for players who didn't confirm/act
                if timed_out:
                    afk_players = await db_manager.execute_query(
                        "SELECT user_id, sanity FROM players WHERE game_id = ? AND (confirmed_action = 0 OR has_acted_this_turn = 0) AND hp > 0",
                        (self.game_id,), fetchall=True
                    )
                    penalty_sanity = 15
                    for player_row in afk_players:
                        new_sanity = max(0, player_row['sanity'] - penalty_sanity)
                        await db_manager.execute_query(
                            "UPDATE players SET sanity = ? WHERE user_id = ? AND game_id = ?",
                            (new_sanity, player_row['user_id'], self.game_id), commit=True
                        )
                        turn_events.append(f"👻 Người chơi bị bỏ qua lượt mất {penalty_sanity} tinh thần!")

                # 2. Process confirmed actions
                actions = await db_manager.execute_query(
                    "SELECT user_id, action_this_turn, background_name FROM players WHERE game_id = ? AND confirmed_action = 1",
                    (self.game_id,), fetchall=True
                )
                
                action_summaries = []
                for action in actions:
                    bg_name = action['background_name']
                    if action['action_this_turn'] == 'search':
                        turn_events.append(f"🔍 {bg_name} tìm kiếm xung quanh...")
                        action_summaries.append('search')
                    elif action['action_this_turn'] == 'attack':
                        turn_events.append(f"⚔️ {bg_name} tấn công vào bóng tối!")
                        action_summaries.append('attack')
                    elif action['action_this_turn'] == 'flee':
                        turn_events.append(f"🏃 {bg_name} chạy thoát!")
                        action_summaries.append('flee')
                
                # 3. Generate LLM narrative
                scene_keywords = [scenario_type, "nguy hiểm"] + action_summaries
                try:
                    summary = await asyncio.wait_for(
                        llm_service.describe_scene(list(set(scene_keywords))),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    summary = f"Lượt {(await db_manager.execute_query('SELECT current_turn FROM active_games WHERE channel_id = ?', (self.game_id,), fetchone=True))['current_turn']}: Tình cảnh ngày càng căng thẳng..."

                # 4. Reset turn states
                await db_manager.execute_query(
                    "UPDATE players SET has_acted_this_turn = 0, action_this_turn = NULL, confirmed_action = 0 WHERE game_id = ?",
                    (self.game_id,), commit=True
                )
                
                print(f"Game {self.game_id}: Turn processed.")
                
                # 5. Publish results
                if self.publish_callback:
                    try:
                        await self.publish_callback(self.game_id, summary, turn_events)
                    except Exception as e:
                        print(f"Game {self.game_id}: Error in publish_callback: {e}")
                
                # 6. Start next turn
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

async def confirm_player_action(user_id: int, game_id: int):
    """Entry point for confirming an action."""
    manager = game_manager.get_manager(game_id)
    return await manager.confirm_action(user_id)