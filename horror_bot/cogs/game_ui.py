import discord
from discord.ext import commands
from services import game_engine
from database import db_manager

# --- Emoji Reactions for Actions ---
ACTION_EMOJIS = {
    "attack": "⚔️",      # Tấn công
    "flee": "🏃",        # Chạy trốn
    "search": "🔍",      # Tìm kiếm
    "confirm": "✅",     # Xác nhận
    "skip": "⏭️"         # Bỏ qua
}

class ActionReactionView(discord.ui.View):
    """Simple emoji reaction handler for game actions."""
    def __init__(self, game_id: int, message_id: int = None):
        super().__init__(timeout=None)
        self.game_id = game_id
        self.message_id = message_id

    # Use raw_reaction_add event listener in main cog instead


class ActionView(discord.ui.View):
    """Legacy button view - kept for compatibility during transition."""
    def __init__(self, game_id: int):
        super().__init__(timeout=None)
        self.game_id = game_id

    @discord.ui.button(label="⚔️ Tấn Công", style=discord.ButtonStyle.danger, custom_id="attack_button")
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
            await game_engine.register_action(interaction.user.id, self.game_id, "attack")
            await interaction.followup.send("✅ Bạn chọn **Tấn Công**! Nhấn nút **XÁC NHẬN** để confirm hành động.", ephemeral=True)
        except discord.errors.NotFound:
            print(f"⚠️ Interaction expired cho user {interaction.user.id}")
        except Exception as e:
            print(f"❌ Lỗi attack button: {e}")

    @discord.ui.button(label="🏃 Chạy Trốn", style=discord.ButtonStyle.secondary, custom_id="flee_button")
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
            await game_engine.register_action(interaction.user.id, self.game_id, "flee")
            await interaction.followup.send("✅ Bạn chọn **Chạy Trốn**! Nhấn nút **XÁC NHẬN** để confirm hành động.", ephemeral=True)
        except discord.errors.NotFound:
            print(f"⚠️ Interaction expired cho user {interaction.user.id}")
        except Exception as e:
            print(f"❌ Lỗi flee button: {e}")

    @discord.ui.button(label="🔍 Tìm Kiếm", style=discord.ButtonStyle.primary, custom_id="search_button")
    async def search(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
            await game_engine.register_action(interaction.user.id, self.game_id, "search")
            await interaction.followup.send("✅ Bạn chọn **Tìm Kiếm**! Nhấn nút **XÁC NHẬN** để confirm hành động.", ephemeral=True)
        except discord.errors.NotFound:
            print(f"⚠️ Interaction expired cho user {interaction.user.id}")
        except Exception as e:
            print(f"❌ Lỗi search button: {e}")
    
    @discord.ui.button(label="✅ XÁC NHẬN", style=discord.ButtonStyle.success, custom_id="confirm_button")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
            success = await game_engine.confirm_player_action(interaction.user.id, self.game_id)
            if success:
                await interaction.followup.send("🎉 Hành động của bạn đã được xác nhận! Đợi người chơi khác...", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ Bạn chưa chọn hành động nào để xác nhận!", ephemeral=True)
        except discord.errors.NotFound:
            print(f"⚠️ Interaction expired cho user {interaction.user.id}")
        except Exception as e:
            print(f"❌ Lỗi confirm button: {e}")


# --- UI Embeds (Display) ---

def create_progress_bar(value: int, max_value: int, length: int = 10) -> str:
    """Creates a simple text-based progress bar."""
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