from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import discord


@dataclass
class Track:
    title: str
    url: str          # 스트리밍 URL
    webpage_url: str  # YouTube 페이지 URL
    thumbnail: str
    duration: int     # 초 단위
    uploader: str
    requester: discord.Member


class GuildMusicState:
    def __init__(self):
        self.queue: deque[Track] = deque()
        self.history: list[Track] = []
        self.current: Track | None = None
        self.volume: float = 0.5
        self.loop: bool = 0
        self.voice_client: discord.VoiceClient | None = None
        self._play_next_callback: callable | None = None  # MusicCore에서 주입

        self.autoplay: bool = False
        self.seed_track: Track | None = None  # 추천의 기준이 되는 곡

    def is_connected(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_connected()

    def is_playing(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_playing()

    def is_paused(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_paused()


# 봇 전체에서 공유되는 싱글톤 상태 저장소
class MusicStateManager:
    _instance: MusicStateManager | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._states: dict[int, GuildMusicState] = {}
        return cls._instance

    def get(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildMusicState()
        return self._states[guild_id]

    def remove(self, guild_id: int):
        self._states.pop(guild_id, None)