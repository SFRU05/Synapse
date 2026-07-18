import discord
from discord.ext import commands
from discord import app_commands

from jumbo_emoji.toggle_store import is_enabled, set_enabled

FEATURE_LABELS = {
    "custom": "커스텀 이모지",
    "unicode": "기본 이모지 확대",
}


def build_status_embed(guild_id: int) -> discord.Embed:
    embed = discord.Embed(title="🔍 점보 이모지 설정", color=discord.Color.blurple())
    for feature, label in FEATURE_LABELS.items():
        state = "🟢 켜짐" if is_enabled(guild_id, feature) else "🔴 꺼짐"
        embed.add_field(name=label, value=state, inline=True)
    embed.set_footer(text="아래 버튼으로 켜고 끌 수 있어요.")
    return embed


class ToggleButton(discord.ui.Button):
    def __init__(self, feature: str, guild_id: int):
        self.feature = feature
        enabled = is_enabled(guild_id, feature)
        label_base = FEATURE_LABELS[feature]
        label = f"{label_base} 끄기" if enabled else f"{label_base} 켜기"
        style = discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success
        super().__init__(label=label, style=style, custom_id=f"jumbo_toggle_{feature}")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("관리자 권한이 필요해요.", ephemeral=True)
            return

        guild_id = interaction.guild_id
        current = is_enabled(guild_id, self.feature)
        set_enabled(guild_id, self.feature, not current)

        new_embed = build_status_embed(guild_id)
        new_view = JumboEmojiSettingsView(guild_id)
        await interaction.response.edit_message(embed=new_embed, view=new_view)


class JumboEmojiSettingsView(discord.ui.View):
    def __init__(self, guild_id: int, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        for feature in FEATURE_LABELS:
            self.add_item(ToggleButton(feature, guild_id))


class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="점보이모지", description="이모지 확대 설정 보기 및 켜기/끄기")
    @app_commands.default_permissions(administrator=True)
    async def emoji_expand(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("관리자 권한이 필요해요.", ephemeral=True)
            return

        embed = build_status_embed(interaction.guild_id)
        view = JumboEmojiSettingsView(interaction.guild_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))