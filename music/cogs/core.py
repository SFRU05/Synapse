from __future__ import annotations
import asyncio
import discord
import yt_dlp
import os
import hashlib
from pathlib import Path
from music.cogs.state import MusicStateManager, Track
from music.cogs.recommender import get_artist_tracks

# 음성 채널 모니터링 타이머
voice_channel_timers = {}

# 캐시 디렉토리 설정 (프로젝트 루트의 music_cache 폴더)
CACHE_DIR = Path("./music_cache")
CACHE_DIR.mkdir(exist_ok=True)

# yt-dlp 기본 옵션
YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    'cookiefile': 'youtube.com_cookies.txt',
    'nocheckcertificate': True,
}

# 파일 재생용 FFmpeg 옵션 (속도 및 싱크 문제 해결)
FFMPEG_OPTS_FILE = {
    "options": "-vn -ar 48000 -ac 2",
}

def _fetch_track(query: str, requester: discord.Member) -> Track | None:
    """yt-dlp로 YouTube 검색 후 Track 객체 반환"""
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
                url=info["url"], # 스트리밍 URL (필요시 대비)
                webpage_url=info.get("webpage_url", ""),
                thumbnail=info.get("thumbnail", ""),
                duration=info.get("duration", 0),
                uploader=info.get("uploader", "알 수 없음"),
                requester=requester,
            )
        except Exception as e:
            print(f"검색 오류: {e}")
            return None

async def fetch_track(query: str, requester: discord.Member) -> Track | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_track, query, requester)

def _download_audio(track: Track) -> str | None:
    """트랙을 파일로 다운로드하고 경로 반환 (캐시 적용)"""
    try:
        # 파일명 생성을 위한 해싱 (URL 기반)
        file_hash = hashlib.md5(track.webpage_url.encode()).hexdigest()
        file_path = CACHE_DIR / f"{file_hash}.mp3"

        # 이미 다운로드된 파일이 있으면 즉시 반환
        if file_path.exists():
            print(f"✅ 캐시 발견: {track.title}")
            return str(file_path)

        # 다운로드 옵션 설정
        ydl_opts_dl = {
            **YDL_OPTS,
            "format": "bestaudio/best",
            "outtmpl": str(CACHE_DIR / f"{file_hash}.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
            print(f"📥 음악을 구성하고 있어요: {track.title}")
            ydl.download([track.webpage_url])
            
        return str(file_path)
    except Exception as e:
        print(f"❌ 재생 오류: {e}")
        return None

async def download_audio(track: Track) -> str | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download_audio, track)

async def monitor_voice_channel(guild_id: int, channel: discord.TextChannel, bot_loop: asyncio.AbstractEventLoop):
    manager = MusicStateManager()
    state = manager.get(guild_id)
    while state.is_connected():
        try:
            if state.voice_client and state.voice_client.channel:
                members_in_channel = [m for m in state.voice_client.channel.members if not m.bot]
                if not members_in_channel:
                    await channel.send(embed=discord.Embed(title="👋 음성 채널 비어있음", description="채널에 아무도 없어 접속을 종료할게요.", color=discord.Color.orange()))
                    state.queue.clear()
                    state.current = None
                    await state.voice_client.disconnect()
                    state.voice_client = None
                    break
            await asyncio.sleep(10)
        except Exception: break
    if guild_id in voice_channel_timers: del voice_channel_timers[guild_id]

def start_voice_monitoring(guild_id: int, channel: discord.TextChannel, bot_loop: asyncio.AbstractEventLoop):
    if guild_id not in voice_channel_timers:
        task = asyncio.ensure_future(monitor_voice_channel(guild_id, channel, bot_loop), loop=bot_loop)
        voice_channel_timers[guild_id] = task

def play_next(guild_id: int, channel: discord.TextChannel, bot_loop: asyncio.AbstractEventLoop):
    manager = MusicStateManager()
    state = manager.get(guild_id)

    if not state.is_connected(): return

    if state.loop == 1 and state.current:
        next_track = state.current
    else:
        if state.current:
            if state.loop == 2: state.queue.append(state.current)
            else: state.history.append(state.current)
        if state.queue: next_track = state.queue.popleft()
        else: next_track = None

    if not next_track:
        if state.autoplay and state.seed_track:
            async def add_artist_tracks():
                try:
                    artist_name = state.seed_track.uploader
                    excluded = {t.title for t in state.history} | {t.title for t in state.queue}
                    if state.current: excluded.add(state.current.title)
                    recs = await get_artist_tracks(artist_name, limit=5, exclude_titles=list(excluded))
                    if recs:
                        for r in recs:
                            state.queue.append(Track(title=r["title"], url=r["url"], webpage_url=r["webpage_url"], thumbnail=r["thumbnail"], duration=r["duration"], uploader=r["uploader"], requester=state.seed_track.requester))
                        play_next(guild_id, channel, bot_loop)
                    else:
                        state.current = None
                        await channel.send(embed=discord.Embed(title="✅ 재생 완료", description="대기열이 끝났어요.", color=discord.Color.green()))
                except Exception: state.current = None
            asyncio.run_coroutine_threadsafe(add_artist_tracks(), bot_loop)
            return
        else:
            state.current = None
            asyncio.run_coroutine_threadsafe(channel.send(embed=discord.Embed(title="✅ 재생 완료", description="대기열이 끝났어요.", color=discord.Color.green())), bot_loop)
            return

    state.current = next_track
    start_voice_monitoring(guild_id, channel, bot_loop)

    # ---------------------------------------------------------
    # 다운로드 후 재생 로직
    # ---------------------------------------------------------
    async def process_and_play():
        # 1. 캐시 확인 (있으면 즉시 재생)
        file_hash = hashlib.md5(next_track.webpage_url.encode()).hexdigest()
        file_path = CACHE_DIR / f"{file_hash}.mp3"

        if not file_path.exists():
            # 2. 캐시 없으면 다운로드 중 메시지
            msg = await channel.send(embed=discord.Embed(title="음악을 구성하고 있어요..", description=f"**{next_track.title}**\n잠시만 기다려 주세요!", color=discord.Color.blue()))
            audio_file = await download_audio(next_track)
            try: await msg.delete()
            except: pass
        else:
            audio_file = str(file_path)

        if audio_file and os.path.exists(audio_file):
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(audio_file, **FFMPEG_OPTS_FILE), volume=state.volume)
            def after_playing(error):
                if error: print(f"재생 오류: {error}")
                play_next(guild_id, channel, bot_loop)
            state.voice_client.play(source, after=after_playing)
            await channel.send(embed=now_playing_embed(next_track))
        else:
            await channel.send(f"⚠️ **{next_track.title}** 다운로드에 실패하여 건너뜁니다.")
            play_next(guild_id, channel, bot_loop)

    asyncio.run_coroutine_threadsafe(process_and_play(), bot_loop)

def now_playing_embed(track: Track) -> discord.Embed:
    mins, secs = divmod(track.duration, 60)
    embed = discord.Embed(title="🎵 지금 재생 중", description=f"**[{track.title}]({track.webpage_url})**", color=discord.Color.blurple())
    if track.thumbnail: embed.set_thumbnail(url=track.thumbnail)
    embed.add_field(name="길이", value=f"{mins}:{secs:02d}")
    embed.add_field(name="업로더", value=track.uploader)
    embed.add_field(name="등록자", value=track.requester.mention)
    return embed
