from __future__ import annotations
import asyncio
import discord
import yt_dlp
from music.cogs.state import MusicStateManager, Track
from music.cogs.recommender import get_artist_tracks

# 음성 채널 모니터링 타이머
voice_channel_timers = {}

YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    'cookiefile': 'youtube.com_cookies.txt'
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


def _fetch_track(query: str, requester: discord.Member) -> Track | None:
    """yt-dlp로 YouTube 검색 후 Track 객체 반환 (동기 함수 — executor에서 실행)"""
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        try:
            if query.startswith("http"):
                info = ydl.extract_info(query, download=False)
            else:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if info and "entries" in info:
                    info = info["entries"][0]

            if not info:
                return None

            return Track(
                title=info.get("title", "알 수 없음"),
                url=info["url"],
                webpage_url=info.get("webpage_url", ""),
                thumbnail=info.get("thumbnail", ""),
                duration=info.get("duration", 0),
                uploader=info.get("uploader", "알 수 없음"),
                requester=requester,
            )
        except Exception:
            return None


async def fetch_track(query: str, requester: discord.Member) -> Track | None:
    """비동기 래퍼"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_track, query, requester)


async def monitor_voice_channel(guild_id: int, channel: discord.TextChannel, bot_loop: asyncio.AbstractEventLoop):
    """음성 채널 모니터링 - 사람이 없으면 나가기"""
    manager = MusicStateManager()
    state = manager.get(guild_id)

    # 모니터링 주기 (30초마다 체크)
    while state.is_connected():
        try:
            # 음성 채널에 사람이 있는지 확인 (봇 제외)
            if state.voice_client and state.voice_client.channel:
                members_in_channel = [m for m in state.voice_client.channel.members if not m.bot]

                # 사람이 없으면 나가기
                if not members_in_channel:
                    embed = discord.Embed(
                        title="👋 음성 채널 비어있음",
                        description="음성 채널",
                        color=discord.Color.orange(),
                    )
                    await channel.send(embed=embed)

                    # 상태 초기화
                    state.queue.clear()
                    state.current = None
                    state.autoplay = False
                    await state.voice_client.disconnect()
                    state.voice_client = None
                    break

            await asyncio.sleep(5)

        except Exception as e:
            print(f"음성 채널 모니터링 오류: {e}")
            break

    # 타이머 정리
    if guild_id in voice_channel_timers:
        del voice_channel_timers[guild_id]


def start_voice_monitoring(guild_id: int, channel: discord.TextChannel, bot_loop: asyncio.AbstractEventLoop):
    """음성 채널 모니터링 시작"""
    if guild_id not in voice_channel_timers:
        task = asyncio.ensure_future(
            monitor_voice_channel(guild_id, channel, bot_loop),
            loop=bot_loop
        )
        voice_channel_timers[guild_id] = task


def stop_voice_monitoring(guild_id: int):
    """음성 채널 모니터링 중지"""
    if guild_id in voice_channel_timers:
        task = voice_channel_timers[guild_id]
        if not task.done():
            task.cancel()
        del voice_channel_timers[guild_id]


def play_next(guild_id: int, channel: discord.TextChannel, bot_loop: asyncio.AbstractEventLoop):
    """현재 곡이 끝난 뒤 호출되는 콜백 — 다음 곡 재생"""
    manager = MusicStateManager()
    state = manager.get(guild_id)

    if not state.is_connected():
        return

    # 1. 한 곡 반복 (state.loop == 1)
    if state.loop == 1 and state.current:
        next_track = state.current

    # 2. 전체 반복 (state.loop == 2) 또는 반복 없음 (state.loop == 0)
    else:
        if state.current:
            if state.loop == 2:
                # 방금 끝난 곡을 대기열의 가장 뒤로 추가 (순환)
                state.queue.append(state.current)
            else:
                # 반복이 꺼진 경우 히스토리에 저장
                state.history.append(state.current)

        if state.queue:
            # 대기열의 맨 앞 곡을 꺼내서 다음 재생 곡으로 설정
            next_track = state.queue.popleft()
        else:
            # 대기열이 완전히 비어있는 경우
            next_track = None

    # 재생할 곡이 없는 경우 처리
    if not next_track:
        # 자동재생 확인
        if state.autoplay and state.seed_track:
            # 자동재생 활성화 + seed 곡이 있으면 작곡가의 곡 자동 추가
            async def add_artist_tracks():
                try:
                    artist_name = state.seed_track.uploader

                    # 히스토리와 현재 대기열의 곡 제목 수집 (제외할 곡들)
                    excluded_titles = set()
                    for track in state.history:
                        excluded_titles.add(track.title)
                    for track in state.queue:
                        excluded_titles.add(track.title)
                    if state.current:
                        excluded_titles.add(state.current.title)

                    recommendations = await get_artist_tracks(artist_name, limit=5,
                                                              exclude_titles=list(excluded_titles))
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

                        # 다시 play_next 호출해서 재생
                        play_next(guild_id, channel, bot_loop)

                        print(f"✅ 자동재생: {artist_name}의 곡 {len(recommendations)}개 추가됨")
                    else:
                        # 추천곡을 찾을 수 없는 경우
                        state.current = None
                        embed = discord.Embed(
                            title="✅ 재생 완료",
                            description="대기열이 모두 끝났어요.",
                            color=discord.Color.green(),
                        )
                        asyncio.run_coroutine_threadsafe(channel.send(embed=embed), bot_loop)
                except Exception as e:
                    print(f"자동재생 오류: {e}")
                    state.current = None
                    embed = discord.Embed(
                        title="✅ 재생 완료",
                        description="대기열이 모두 끝났어요.",
                        color=discord.Color.green(),
                    )
                    asyncio.run_coroutine_threadsafe(channel.send(embed=embed), bot_loop)

            asyncio.run_coroutine_threadsafe(add_artist_tracks(), bot_loop)
            return
        else:
            # 자동재생이 꺼져 있거나 seed_track이 없는 경우
            state.current = None
            embed = discord.Embed(
                title="✅ 재생 완료",
                description="대기열이 모두 끝났어요.",
                color=discord.Color.green(),
            )
            asyncio.run_coroutine_threadsafe(channel.send(embed=embed), bot_loop)
            return

    # 현재 재생 중인 곡 정보 업데이트
    state.current = next_track
    # ----------------------------

    # 음성 채널 모니터링 시작
    start_voice_monitoring(guild_id, channel, bot_loop)

    source = discord.PCMVolumeTransformer(
        discord.FFmpegPCMAudio(next_track.url, **FFMPEG_OPTS),
        volume=state.volume,
    )

    def after_playing(error):
        if error:
            embed = discord.Embed(
                title="⚠️ 재생 오류",
                description=str(error),
                color=discord.Color.red(),
            )
            asyncio.run_coroutine_threadsafe(channel.send(embed=embed), bot_loop)

        # 다음 곡 재생을 위해 play_next 재귀 호출
        play_next(guild_id, channel, bot_loop)

    # 오디오 재생 실행
    state.voice_client.play(source, after=after_playing)

    # 지금 재생 중 알림 전송
    asyncio.run_coroutine_threadsafe(
        channel.send(embed=now_playing_embed(next_track)), bot_loop
    )


def now_playing_embed(track: Track) -> discord.Embed:
    mins, secs = divmod(track.duration, 60)
    embed = discord.Embed(
        title="🎵 지금 재생 중",
        description=f"**[{track.title}]({track.webpage_url})**",
        color=discord.Color.blurple(),
    )
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    embed.add_field(name="길이", value=f"{mins}:{secs:02d}")
    embed.add_field(name="업로더", value=track.uploader)
    embed.add_field(name="등록자", value=track.requester.mention)
    return embed