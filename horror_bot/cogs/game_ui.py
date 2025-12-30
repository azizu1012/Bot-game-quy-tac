# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from services import game_engine
from database import db_manager
import asyncio

# --- Emoji Reactions for Actions ---
ACTION_EMOJIS = {
    "attack": "⚔️",      # Tấn công
    "flee": "🏃",        # Chạy trốn
    "search": "🔍",      # Tìm kiếm
    "confirm": "✅",     # Xác nhận
    "skip": "⏭️"         # Bỏ qua
}

# --- PLAIN TEXT UI FUNCTIONS ---

async def send_action_menu(channel: discord.TextChannel, game_id: int) -> discord.Message:
    """Send action menu using plain text + emoji reactions."""
    text = """**━━━━━━━━━━━━━━━━━━━**
**⚔️ CHỌN HÀNH ĐỘNG:**

Phản ứng bằng emoji để chọn:
⚔️  Tấn Công
🏃  Chạy Trốn
🔍  Tìm Kiếm
✅  Xác Nhận Hành Động
⏭️  Bỏ Qua

**━━━━━━━━━━━━━━━━━━━**"""

    msg = await channel.send(text)
    
    # Add emoji reactions
    for emoji in ACTION_EMOJIS.values():
        try:
            await msg.add_reaction(emoji)
        except:
            pass
    
    return msg


async def send_game_status_plain_text(channel: discord.TextChannel, players: list, turn: int, remaining_time: int = None) -> str:
    """Send game status as plain text (not embed)."""
    status_text = f"""**━━━━━━━━━━━━━━━━━━━**
**LƯỢT {turn}**

**👥 TRẠNG THÁI NGƯỜI CHƠI:**"""

    for player in players:
        hp_bar = create_progress_bar(player['hp'], 120)
        sanity_bar = create_progress_bar(player['sanity'], 120)
        status = "🟢 Sống" if player['hp'] > 0 else "❌ Chết"
        
        status_text += f"""
{status} **{player['name']}** ({player['background']})
❤️  {hp_bar}
🧠 {sanity_bar}
⚡ AGI: {player['agi']}/100 | 🎯 ACC: {player['acc']}/100
"""

    if remaining_time:
        mins = remaining_time // 60
        secs = remaining_time % 60
        status_text += f"\n**⏱️ Thời gian còn lại: {mins}:{secs:02d}**"

    status_text += "\n**━━━━━━━━━━━━━━━━━━━**"
    
    return status_text


def create_progress_bar(value: int, max_value: int, length: int = 10) -> str:
    """Creates a simple text-based progress bar."""
    if max_value == 0:
        ratio = 0
    else:
        ratio = max(0, min(1, value / max_value))
    filled_length = int(length * ratio)
    bar = '█' * filled_length + '░' * (length - filled_length)
    return f"[{bar}] {value}/{max_value}"


class PlayerProfileEmbed(discord.Embed):
    """Embed hiển thị profile của một người chơi khi họ join (chỉ user thấy được)."""
    def __init__(self, player_name: str, background_name: str, background_description: str, 
                 hp: int, sanity: int, agi: int, acc: int):
        super().__init__(
            title=f"👤 {player_name}",
            description=f"**Nghề Nghiệp:** {background_name}\n\n*{background_description}*",
            color=discord.Color.blue()
        )
        
        hp_bar = create_progress_bar(hp, 120)
        sanity_bar = create_progress_bar(sanity, 120)
        
        
        self.add_field(name="❤️ HP", value=hp_bar, inline=False)
        self.add_field(name="🧠 Sanity", value=sanity_bar, inline=False)
        self.add_field(name="⚡ Agility", value=f"`{agi}/100`", inline=True)
        self.add_field(name="🎯 Accuracy", value=f"`{acc}/100`", inline=True)
        
        self.set_footer(text="📱 Chỉ số của bạn trong cuộc phiêu lưu này (chỉ bạn thấy)")

class PlayerDashboardEmbed(discord.Embed):
    """Embed hiển thị toàn bộ thông số của tất cả người chơi."""
    def __init__(self, players_data: list, turn: int):
        super().__init__(
            title=f"👥 BẢNG THÔNG SỐ CÁC NGƯỜI CHƠI - LƯỢT {turn}",
            color=discord.Color.dark_gold()
        )
        
        for player in players_data:
            hp_bar = create_progress_bar(player['hp'], 120)
            sanity_bar = create_progress_bar(player['sanity'], 120)
            acted_emoji = "✅" if player['has_acted'] else "⏳"
            status_emoji = "❌" if player['hp'] <= 0 else "🟢"
            
            player_info = f"{status_emoji} **{player['name']} ({player['background']})**\n"
            player_info += f"❤️ {hp_bar}\n"
            player_info += f"🧠 {sanity_bar}\n"
            player_info += f"⚡ {player['agi']}/100 | 🎯 {player['acc']}/100\n"
            player_info += f"Hành động: {acted_emoji}"
            
            self.add_field(name="", value=player_info, inline=False)
        
        self.set_footer(text="📊 Bảng xếp hạng toàn game")

class GameDashboard(discord.Embed):
    """A custom Embed to display the game's state with expanded scene description."""
    def __init__(self, scene_description: str, players_status: list, turn: int, countdown: int = None, phase: str = "action"):
        # Display scene directly without code block (allow text to expand)
        description = f"**{scene_description}**"
        if countdown is not None:
            countdown_text = f"{countdown // 60}:{countdown % 60:02d}" if countdown > 0 else "0:00"
            description += f"\n\n⏱️ **Thời gian còn lại: {countdown_text}**"
        
        if phase == "thinking":
            description += "\n\n💭 *Giai đoạn bàn bạc - Các người chơi tụ họp lại để thảo luận...*"
        
        super().__init__(
            title=f"🎮 LƯỢT {turn}",
            description=description,
            color=discord.Color.dark_red()
        )
        self.set_author(name="🕷️ QUY TẮC BÓNG TỐI")
        
        status_text = ""
        for player in players_status:
            hp_bar = create_progress_bar(player['hp'], 120)
            sanity_bar = create_progress_bar(player['sanity'], 120)
            acted_emoji = "✅" if player['has_acted'] else "⏳"
            status_emoji = "❌" if player['hp'] <= 0 else "🟢"
            status_text += f"{status_emoji} {acted_emoji} **{player['name']}**\n"
            status_text += f"❤️ {hp_bar} | 🧠 {sanity_bar}\n\n"
            
        if not status_text:
            status_text = "Không có người chơi trong trò chơi."

        self.add_field(name="👥 TRẠNG THÁI", value=status_text, inline=False)
        if phase == "action":
            self.add_field(
                name="⚔️ HÀNH ĐỘNG",
                value="Phản ứng bằng emoji:\n⚔️ Tấn Công | 🏃 Chạy Trốn | 🔍 Tìm Kiếm | ✅ Xác Nhận | ⏭️ Bỏ Qua",
                inline=False
            )
        self.set_footer(text=f"Phase: {phase} | Đợi tất cả người chơi tương tác...")


# --- Cog for loading the persistent view ---

class GameUICog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("✅ Game UI Cog sẵn sàng.")
        # Load all active game views from database
        await self.load_active_game_views()

    async def load_active_game_views(self):
        """Load ActionView for all active games from database."""
        active_games = await db_manager.execute_query(
            "SELECT channel_id FROM active_games WHERE is_active = 1",
            fetchall=True
        )
        if active_games:
            for game in active_games:
                game_id = game['channel_id']
                self.bot.add_view(ActionView(game_id=game_id))
                print(f"✅ Đã tải ActionView cho trò chơi {game_id}")

async def setup(bot: commands.Bot):
    await bot.add_cog(GameUICog(bot))