import discord
from discord import app_commands
from discord.ext import commands
from database import db_manager
from database.db_manager import setup_database
from services import map_generator, game_engine
from cogs.game_ui import GameDashboard, ActionView
import os
import json

class GameCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Game Commands Cog is ready.")
        await setup_database()

    @app_commands.command(name="newgame", description="Starts a new horror RPG game in this channel.")
    @app_commands.describe(scenario="Choose the scenario for the game.")
    @app_commands.choices(scenario=[
        app_commands.Choice(name="Cursed Hotel", value="hotel"),
        app_commands.Choice(name="Abandoned Asylum", value="hospital"),
    ])
    async def new_game(self, interaction: discord.Interaction, scenario: app_commands.Choice[str]):
        game_id = interaction.channel_id
        host_id = interaction.user.id

        if await db_manager.execute_query("SELECT 1 FROM active_games WHERE channel_id = ? AND is_active = 1", (game_id,), fetchone=True):
            await interaction.response.send_message("A game is already active in this channel. Use `/endgame` to stop it.", ephemeral=True)
            return

        await interaction.response.send_message(f"A new game of **{scenario.name}** is starting! Type `/join` to enter.", ephemeral=False)

        scenario_file = f"data/scenarios/{scenario.value}.json"
        game_map = map_generator.generate_map_structure(scenario_file)
        if not game_map:
            await interaction.followup.send("Error: Could not generate the game map.", ephemeral=True)
            return
        
        await db_manager.execute_query(
            "INSERT OR REPLACE INTO active_games (channel_id, host_id, scenario_type) VALUES (?, ?, ?)",
            (game_id, host_id, scenario.value), commit=True
        )
        await db_manager.execute_query(
            "INSERT OR REPLACE INTO game_maps (game_id, map_data) VALUES (?, ?)",
            (game_id, json.dumps(game_map.nodes)), commit=True
        )

        await self.add_player_to_game(host_id, game_id, game_map.start_node_id)
        
        turn_manager = game_engine.game_manager.get_manager(game_id, publish_callback=self.publish_turn_results)
        await turn_manager.start_turn()

        message = await self.update_dashboard(interaction.channel, scene_description="The adventure begins...")
        if message:
            await db_manager.execute_query(
                "UPDATE active_games SET dashboard_message_id = ? WHERE channel_id = ?",
                (message.id, game_id), commit=True
            )

    @app_commands.command(name="join", description="Joins the currently active game.")
    async def join_game(self, interaction: discord.Interaction):
        game_id = interaction.channel_id
        user_id = interaction.user.id

        game = await db_manager.execute_query("SELECT 1 FROM active_games WHERE channel_id = ? AND is_active = 1", (game_id,), fetchone=True)
        if not game:
            await interaction.response.send_message("There is no active game in this channel.", ephemeral=True)
            return

        if await db_manager.execute_query("SELECT 1 FROM players WHERE user_id = ? AND game_id = ?", (user_id, game_id), fetchone=True):
            await interaction.response.send_message("You are already in this game.", ephemeral=True)
            return

        game_map_data = await db_manager.execute_query("SELECT map_data FROM game_maps WHERE game_id = ?", (game_id,), fetchone=True)
        if not game_map_data or not game_map_data['map_data']:
             await interaction.response.send_message("Error: Couldn't load map data for this game.", ephemeral=True)
             return

        map_nodes = json.loads(game_map_data['map_data'])
        start_node_id = list(map_nodes.keys())[0] if map_nodes else None
        
        if not start_node_id:
             await interaction.response.send_message("Error: Game map is corrupted or empty.", ephemeral=True)
             return

        await self.add_player_to_game(user_id, game_id, start_node_id)
        await interaction.response.send_message(f"{interaction.user.mention} has joined the game!", ephemeral=False)
        await self.update_dashboard(interaction.channel, scene_description=f"{interaction.user.display_name} has entered the fray...")

    async def add_player_to_game(self, user_id, game_id, start_location_id):
        background_id = "athlete"
        await db_manager.execute_query(
            "INSERT INTO players (user_id, game_id, background_id, current_location_id) VALUES (?, ?, ?, ?)",
            (user_id, game_id, background_id, start_location_id), commit=True
        )

    async def publish_turn_results(self, game_id: int, summary: str, turn_events: list[str]):
        channel = self.bot.get_channel(game_id)
        if not channel: return
        full_description = f"{summary}\n\n" + "\n".join(f"- {event}" for event in turn_events)
        await self.update_dashboard(channel, scene_description=full_description)

    async def update_dashboard(self, channel: discord.TextChannel, scene_description: str = "The situation is tense...") -> discord.Message | None:
        game = await db_manager.execute_query("SELECT * FROM active_games WHERE channel_id = ? AND is_active = 1", (channel.id,), fetchone=True)
        if not game: return

        players = await db_manager.execute_query("SELECT * FROM players WHERE game_id = ?", (channel.id,), fetchall=True)
        
        player_statuses = []
        for p in players:
            user = self.bot.get_user(p['user_id']) or await self.bot.fetch_user(p['user_id'])
            if user:
                player_statuses.append({'name': user.display_name, 'hp': p['hp'], 'sanity': p['sanity'], 'has_acted': p['has_acted_this_turn']})

        dashboard = GameDashboard(scene_description=scene_description, players_status=player_statuses, turn=game['current_turn'])
        view = ActionView(game_id=channel.id)
        
        message_id = game['dashboard_message_id']
        message = None
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=dashboard, view=view)
            except discord.NotFound:
                message = None 

        if not message:
            message = await channel.send(embed=dashboard, view=view)
            await db_manager.execute_query("UPDATE active_games SET dashboard_message_id = ? WHERE channel_id = ?", (message.id, channel.id), commit=True)
        
        return message

async def setup(bot: commands.Bot):
    await bot.add_cog(GameCommands(bot))