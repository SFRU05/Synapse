from __future__ import annotations
import discord
from music.cogs.state import MusicStateManager

volume_cmd = discord.app_commands.Group(name="볼륨", description="볼륨 관련 명령어")
manager = MusicStateManager()


def _footer(embed: discord.Embed, interaction: discord.Interaction) -> discord.Embed:
    embed.set_footer(
        text=f"요청자: {interaction.user.display_name}",
        icon_url=interaction.user.display_avatar.url,
    )
    return embed


def _volume_bar(value: int) -> str:
    filled = round(value / 10)
    return "🟦" * filled + "⬛" * (10 - filled)


@volume_cmd.command(name="설정", description="볼륨을 설정해요. (0% ~ 100%)")
@discord.app_commands.describe(value="설정할 볼륨 (0% ~ 100%)")
async def set_volume(interaction: discord.Interaction, value: int):
    if not 0 <= value <= 100:
        embed = _footer(discord.Embed(title="❌ 오류", description="볼륨은 0% ~ 100% 사이로 설정해 주세요.", color=discord.Color.red()), interaction)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    state = manager.get(interaction.guild_id)
    state.volume = value / 100

    # 현재 재생 중이면 즉시 적용
    if state.is_playing() and state.voice_client.source:
        state.voice_client.source.volume = state.volume

    embed = discord.Embed(
        title="🔊 볼륨 설정",
        description=f"{_volume_bar(value)} **{value}%**",
        color=discord.Color.blurple(),
    )
    _footer(embed, interaction)
    await interaction.response.send_message(embed=embed)


@volume_cmd.command(name="확인", description="현재 볼륨을 확인해요.")
async def get_volume(interaction: discord.Interaction):
    state = manager.get(interaction.guild_id)
    current = int(state.volume * 100)

    embed = discord.Embed(
        title="🔊 현재 볼륨",
        description=f"{_volume_bar(current)} **{current}%**",
        color=discord.Color.blurple(),
    )
    _footer(embed, interaction)
    await interaction.response.send_message(embed=embed)