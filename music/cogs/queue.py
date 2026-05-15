from __future__ import annotations
import random
import discord
from music.cogs.state import MusicStateManager

queue_cmd = discord.app_commands.Group(name="대기열", description="대기열 관련 명령어")
manager = MusicStateManager()


def _footer(embed: discord.Embed, interaction: discord.Interaction) -> discord.Embed:
    embed.set_footer(
        text=f"요청자: {interaction.user.display_name}",
        icon_url=interaction.user.display_avatar.url,
    )
    return embed


async def _check_voice_connection(interaction: discord.Interaction) -> bool:
    """유저와 봇의 채널 상태를 확인하는 공통 함수"""
    if not interaction.user.voice:
        embed = _footer(discord.Embed(title="❌ 오류", description="먼저 음성 채널에 들어가 주세요.", color=discord.Color.red()),
                        interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False

    state = manager.get(interaction.guild_id)
    if state.voice_client and interaction.user.voice.channel != state.voice_client.channel:
        embed = _footer(discord.Embed(title="❌ 오류", description="봇과 같은 음성 채널에 있어야 합니다.", color=discord.Color.red()),
                        interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False
    return True


@queue_cmd.command(name="확인", description="현재 대기열을 표시합니다.")
async def show_queue(interaction: discord.Interaction):
    state = manager.get(interaction.guild_id)

    if not state.current and not state.queue:
        embed = _footer(discord.Embed(title="📋 대기열", description="대기열이 비어있어요.", color=discord.Color.blurple()),
                        interaction)
        return await interaction.response.send_message(embed=embed)

    embed = discord.Embed(title="📋 대기열", color=discord.Color.blurple())

    # --- 반복 재생 상태 메시지 추가 ---
    loop_status = ""
    if state.loop == 1:
        loop_status = "\n\n🔂 **현재 곡 반복 재생 중**"
    elif state.loop == 2:
        loop_status = "\n\n🔁 **전체 곡 반복 재생 중**"
    # state.loop == 0 (꺼짐)일 때는 아무것도 추가하지 않음

    if state.current:
        mins, secs = divmod(state.current.duration, 60)
        embed.add_field(
            name="🎵 지금 재생 중",
            value=f"**[{state.current.title}]({state.current.webpage_url})**\n"
                  f"길이: `{mins}:{secs:02d}` · 등록자: {state.current.requester.mention}"
                  f"{loop_status}",  # 여기에 반복 상태 표시
            inline=False,
        )

    if state.queue:
        lines = []
        for i, track in enumerate(list(state.queue)[:10]):
            mins, secs = divmod(track.duration, 60)
            lines.append(f"`{i + 1}.` **{track.title}** `{mins}:{secs:02d}` · {track.requester.mention}")
        if len(state.queue) > 10:
            lines.append(f"*... 외 {len(state.queue) - 10}곡*")
        embed.add_field(name=f"다음 곡 ({len(state.queue)}곡)", value="\n".join(lines), inline=False)

    _footer(embed, interaction)
    await interaction.response.send_message(embed=embed)


@queue_cmd.command(name="삭제", description="대기열에서 특정 곡을 삭제합니다.")
@discord.app_commands.describe(index="삭제할 곡 번호")
async def remove(interaction: discord.Interaction, index: int):
    # 통화방 체크
    if not await _check_voice_connection(interaction): return

    state = manager.get(interaction.guild_id)

    if not state.queue:
        embed = _footer(discord.Embed(title="❌ 오류", description="대기열이 비어있어요.", color=discord.Color.red()), interaction)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    if not 1 <= index <= len(state.queue):
        embed = _footer(discord.Embed(title="❌ 오류", description=f"1~{len(state.queue)} 사이의 번호를 입력해 주세요.",
                                      color=discord.Color.red()), interaction)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    queue_list = list(state.queue)
    removed = queue_list.pop(index - 1)
    state.queue.clear()
    state.queue.extend(queue_list)

    embed = discord.Embed(
        title="🗑️ 곡 삭제",
        description=f"**{removed.title}** 을 대기열에서 삭제했어요.\n등록자: {removed.requester.mention}",
        color=discord.Color.red(),
    )
    _footer(embed, interaction)
    await interaction.response.send_message(embed=embed)


@queue_cmd.command(name="초기화", description="대기열을 전부 비웁니다.")
async def clear(interaction: discord.Interaction):
    # 통화방 체크
    if not await _check_voice_connection(interaction): return

    state = manager.get(interaction.guild_id)
    count = len(state.queue)
    state.queue.clear()

    embed = discord.Embed(
        title="🗑️ 대기열 초기화",
        description=f"대기열의 곡 **{count}개**를 전부 삭제했어요.",
        color=discord.Color.red(),
    )
    _footer(embed, interaction)
    await interaction.response.send_message(embed=embed)


@queue_cmd.command(name="셔플", description="대기열을 무작위로 섞습니다.")
async def shuffle(interaction: discord.Interaction):
    # 통화방 체크
    if not await _check_voice_connection(interaction): return

    state = manager.get(interaction.guild_id)

    if len(state.queue) < 2:
        embed = _footer(discord.Embed(title="❌ 오류", description="셔플하려면 대기열에 2곡 이상 있어야 해요.", color=discord.Color.red()),
                        interaction)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    queue_list = list(state.queue)
    random.shuffle(queue_list)
    state.queue.clear()
    state.queue.extend(queue_list)

    embed = discord.Embed(
        title="🔀 셔플",
        description=f"대기열 **{len(queue_list)}곡**을 무작위로 섞었어요.",
        color=discord.Color.green(),
    )
    _footer(embed, interaction)
    await interaction.response.send_message(embed=embed)