from __future__ import annotations
import discord
from music.cogs.state import MusicStateManager, Track
from music.cogs.core import fetch_track, play_next, now_playing_embed
from music.cogs.recommender import get_artist_tracks

playback_cmd = discord.app_commands.Group(name="재생", description="재생 관련 명령어")
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


# --- 반복 재생 드롭다운 관련 클래스 ---

class LoopSelect(discord.ui.Select):
    def __init__(self, state):
        self.state = state
        options = [
            discord.SelectOption(label="반복 끔", description="반복 재생을 하지 않습니다.", emoji="➡️", value="0"),
            discord.SelectOption(label="1곡 반복", description="현재 곡을 계속 재생합니다.", emoji="🔂", value="1"),
            discord.SelectOption(label="전체 반복", description="대기열 전체를 반복합니다.", emoji="🔁", value="2")
        ]
        super().__init__(placeholder="반복 모드를 선택하세요...", options=options)

    async def callback(self, interaction: discord.Interaction):
        # 조작 시점에 다시 한번 채널 확인
        if not await _check_voice_connection(interaction):
            return

        self.state.loop = int(self.values[0])
        status_text = {0: "반복 끔 ➡️", 1: "1곡 반복 🔂", 2: "전체 반복 🔁"}
        selected_status = status_text[self.state.loop]

        embed = discord.Embed(
            title="🔁 반복 설정 완료",
            description=f"반복 모드가 **{selected_status}**으로 변경되었습니다.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class LoopView(discord.ui.View):
    def __init__(self, state):
        super().__init__()
        self.add_item(LoopSelect(state))


# --- 명령어 정의 ---

@playback_cmd.command(name="시작", description="YouTube에서 곡을 검색하거나 URL로 재생합니다.")
@discord.app_commands.describe(query="곡 이름 또는 YouTube URL")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        embed = _footer(discord.Embed(title="❌ 오류", description="먼저 음성 채널에 들어가 주세요.", color=discord.Color.red()),
                        interaction)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    await interaction.response.defer()
    state = manager.get(interaction.guild_id)

    if not state.is_connected():
        state.voice_client = await interaction.user.voice.channel.connect(self_deaf=True)
    elif interaction.user.voice.channel != state.voice_client.channel:
        await state.voice_client.move_to(interaction.user.voice.channel)

    searching_embed = _footer(discord.Embed(title="🔍 검색 중...", description=f"`{query}`", color=discord.Color.blurple()),
                              interaction)
    await interaction.followup.send(embed=searching_embed)

    track = await fetch_track(query, interaction.user)
    if not track:
        embed = _footer(discord.Embed(title="❌ 오류", description="곡을 찾을 수 없어요.", color=discord.Color.red()), interaction)
        return await interaction.edit_original_response(embed=embed)

    state.queue.append(track)

    if not state.is_playing():
        play_next(interaction.guild_id, interaction.channel, interaction.client.loop)
    else:
        pos = len(state.queue)
        mins, secs = divmod(track.duration, 60)
        embed = discord.Embed(
            title="📋 대기열에 추가됨",
            description=f"**[{track.title}]({track.webpage_url})**",
            color=discord.Color.green(),
        )
        embed.add_field(name="길이", value=f"{mins}:{secs:02d}")
        embed.add_field(name="대기열 순서", value=f"#{pos}")
        embed.add_field(name="등록자", value=track.requester.mention)
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        _footer(embed, interaction)
        await interaction.edit_original_response(embed=embed)


@playback_cmd.command(name="일시정지", description="재생을 일시정지합니다.")
async def pause(interaction: discord.Interaction):
    if not await _check_voice_connection(interaction): return
    state = manager.get(interaction.guild_id)

    if not state.is_playing():
        embed = _footer(discord.Embed(title="❌ 오류", description="재생 중인 곡이 없어요.", color=discord.Color.red()),
                        interaction)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    state.voice_client.pause()
    embed = _footer(discord.Embed(title="⏸️ 일시정지", description="재생을 일시정지했어요.", color=discord.Color.yellow()),
                    interaction)
    await interaction.response.send_message(embed=embed)


@playback_cmd.command(name="계속", description="일시정지된 재생을 계속합니다.")
async def resume(interaction: discord.Interaction):
    if not await _check_voice_connection(interaction): return
    state = manager.get(interaction.guild_id)

    if not state.is_paused():
        embed = _footer(discord.Embed(title="❌ 오류", description="일시정지된 곡이 없어요.", color=discord.Color.red()),
                        interaction)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    state.voice_client.resume()
    embed = _footer(discord.Embed(title="▶️ 재생 재개", description="계속 재생할게요.", color=discord.Color.green()), interaction)
    await interaction.response.send_message(embed=embed)


@playback_cmd.command(name="정지", description="재생을 멈추고 대기열을 초기화합니다.")
async def stop(interaction: discord.Interaction):
    if not await _check_voice_connection(interaction): return
    state = manager.get(interaction.guild_id)

    state.queue.clear()
    state.current = None
    if state.voice_client:
        state.voice_client.stop()
        await state.voice_client.disconnect()
        state.voice_client = None

    embed = _footer(discord.Embed(title="⏹️ 정지", description="재생을 멈추고 채널에서 나왔어요.", color=discord.Color.red()),
                    interaction)
    await interaction.response.send_message(embed=embed)


@playback_cmd.command(name="다음", description="다음 곡으로 넘어갑니다.")
async def skip(interaction: discord.Interaction):
    if not await _check_voice_connection(interaction): return
    state = manager.get(interaction.guild_id)

    if not state.is_playing():
        embed = _footer(discord.Embed(title="❌ 오류", description="재생 중인 곡이 없어요.", color=discord.Color.red()),
                        interaction)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    state.voice_client.stop()
    embed = _footer(discord.Embed(title="⏭️ 다음 곡", description="다음 곡으로 넘어갈게요.", color=discord.Color.blurple()),
                    interaction)
    await interaction.response.send_message(embed=embed)


@playback_cmd.command(name="이전", description="이전 곡으로 돌아갑니다.")
async def prev(interaction: discord.Interaction):
    if not await _check_voice_connection(interaction): return
    state = manager.get(interaction.guild_id)

    if not state.history:
        embed = _footer(discord.Embed(title="❌ 오류", description="이전 곡이 없어요.", color=discord.Color.red()), interaction)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    prev_track = state.history.pop()
    if state.current:
        state.queue.appendleft(state.current)
    state.queue.appendleft(prev_track)
    state.current = None

    if state.is_playing():
        state.voice_client.stop()
    else:
        play_next(interaction.guild_id, interaction.channel, interaction.client.loop)

    embed = _footer(discord.Embed(title="⏮️ 이전 곡", description="이전 곡으로 돌아갈게요.", color=discord.Color.blurple()),
                    interaction)
    await interaction.response.send_message(embed=embed)


@playback_cmd.command(name="지금", description="현재 재생 중인 곡 정보를 표시합니다.")
async def nowplaying(interaction: discord.Interaction):
    state = manager.get(interaction.guild_id)
    if not state.current:
        embed = _footer(discord.Embed(title="❌ 오류", description="재생 중인 곡이 없어요.", color=discord.Color.red()),
                        interaction)
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    embed = now_playing_embed(state.current)
    await interaction.response.send_message(embed=embed)


@playback_cmd.command(name="반복", description="반복 모드를 설정합니다.")
async def loop(interaction: discord.Interaction):
    if not await _check_voice_connection(interaction): return
    state = manager.get(interaction.guild_id)

    current_status = {0: "끔", 1: "1곡 반복", 2: "전체 반복"}.get(state.loop, "알 수 없음")

    embed = discord.Embed(
        title="🔁 반복 재생 설정",
        description=f"현재 설정: **{current_status}**\n아래 메뉴에서 변경할 모드를 선택해주세요.",
        color=discord.Color.blurple()
    )
    # 이 명령어는 ephemeral=True를 쓰면 본인만 메뉴가 보입니다. 취향껏 설정하세요.
    await interaction.response.send_message(embed=embed, view=LoopView(state), ephemeral=True)


@playback_cmd.command(name="자동재생", description="작곡가의 다른 음악을 자동재생합니다.")
async def autoplay(interaction: discord.Interaction):
    await interaction.response.defer()
    state = manager.get(interaction.guild_id)

    if not state.current:
        embed = _footer(discord.Embed(title="❌ 오류", description="먼저 곡을 재생해주세요.", color=discord.Color.red()),
                        interaction)
        return await interaction.followup.send(embed=embed)

    state.autoplay = not state.autoplay

    if state.autoplay:
        state.seed_track = state.current  # 현재 곡을 기준으로 설정
        artist_name = state.current.uploader  # 업로더(작곡가)명 사용

        # 자동재생 활성화 시 작곡가의 다른 곡 5개를 대기열에 추가
        try:
            # 히스토리와 현재 대기열의 곡 제목 수집 (제외할 곡들)
            excluded_titles = set()
            for track in state.history:
                excluded_titles.add(track.title)
            for track in state.queue:
                excluded_titles.add(track.title)
            if state.current:
                excluded_titles.add(state.current.title)

            recommendations = await get_artist_tracks(
                artist_name,
                limit=5,
                exclude_titles=list(excluded_titles)
            )

            if recommendations:
                for rec in recommendations:
                    recommended_track = Track(
                        title=rec["title"],
                        url=rec["url"],
                        webpage_url=rec["webpage_url"],
                        thumbnail=rec["thumbnail"],
                        duration=rec["duration"],
                        uploader=rec["uploader"],
                        requester=state.seed_track.requester,
                    )
                    state.queue.append(recommended_track)
                print(f"✅ {artist_name}의 곡 {len(recommendations)}개 대기열에 추가됨")
        except Exception as e:
            print(f"작곡가 음악 추가 오류: {e}")

        embed = discord.Embed(
            title="✅ 자동재생 활성화",
            description=f"**{state.current.uploader}**의 다른 음악을 자동으로 재생할게요.\n곡 5개를 대기열에 추가했습니다.",
            color=discord.Color.green(),
        )
    else:
        embed = discord.Embed(
            title="❌ 자동재생 비활성화",
            description="더 이상 자동재생하지 않습니다.",
            color=discord.Color.red(),
        )

    _footer(embed, interaction)
    await interaction.followup.send(embed=embed)


@playback_cmd.command(name="나가", description="봇을 음성 채널에서 내보냅니다.")
async def leave(interaction: discord.Interaction):
    if not await _check_voice_connection(interaction): return
    state = manager.get(interaction.guild_id)

    state.queue.clear()
    state.current = None
    state.autoplay = False
    if state.voice_client:
        await state.voice_client.disconnect()
        state.voice_client = None

    embed = _footer(discord.Embed(title="👋 퇴장", description="채널에서 나왔어요.", color=discord.Color.blurple()), interaction)
    await interaction.response.send_message(embed=embed)