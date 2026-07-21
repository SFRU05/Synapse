import discord
from discord import app_commands
from discord.ext import commands
from gtts import gTTS
import asyncio
import os
import uuid

LANG_CHOICES = {
    "한국어": "ko",
    "영어(미국)": "en",
    "일본어": "ja",
}

SPEED_CHOICES = {
    "보통": False,   # gTTS slow=False
    "느리게": True,  # gTTS slow=True
}


class TTSCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild_settings: dict[int, dict] = {}
        self.voice_queues: dict[int, asyncio.Queue] = {}
        self.voice_tasks: dict[int, asyncio.Task] = {}
        os.makedirs("tts_temp", exist_ok=True)

    def get_settings(self, guild_id: int) -> dict:
        if guild_id not in self.guild_settings:
            self.guild_settings[guild_id] = {
                "enabled": False,
                "lang": "ko",
                "slow": False,
            }
        return self.guild_settings[guild_id]

    async def generate_tts(self, text: str, lang: str, slow: bool, filename: str):
        tts = gTTS(text=text, lang=lang, slow=slow)
        tts.save(filename)

    async def process_voice_queue(self, guild_id: int, voice_client: discord.VoiceClient):
        queue = self.voice_queues[guild_id]
        while True:
            filename = await queue.get()
            try:
                while voice_client.is_playing() or voice_client.is_paused():
                    await asyncio.sleep(0.2)

                finished = asyncio.Event()

                def after_play(error):
                    if error:
                        print(f"[TTS 재생 오류] {error}")
                    self.bot.loop.call_soon_threadsafe(finished.set)

                source = discord.FFmpegPCMAudio(filename)
                voice_client.play(source, after=after_play)
                await finished.wait()
            finally:
                if os.path.exists(filename):
                    os.remove(filename)
                queue.task_done()

    tts_group = app_commands.Group(name="tts", description="TTS 명령어")

    @tts_group.command(name="열기", description="TTS 설정창을 엽니다.")
    async def tts_open(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("서버에서만 사용 가능해요.", ephemeral=True)

        settings = self.get_settings(interaction.guild.id)
        embed = self.build_settings_embed(settings)
        view = TTSSettingsView(self, interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @tts_group.command(name="종료", description="TTS를 비활성화하고 음성 채널에서 퇴장합니다.")
    async def tts_stop(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("서버에서만 사용 가능해요.", ephemeral=True)

        guild_id = interaction.guild.id
        vc = interaction.guild.voice_client

        if vc and vc.is_connected():
            await vc.disconnect()

        if guild_id in self.voice_tasks:
            self.voice_tasks[guild_id].cancel()
            del self.voice_tasks[guild_id]
        if guild_id in self.voice_queues:
            del self.voice_queues[guild_id]

        self.get_settings(guild_id)["enabled"] = False
        await interaction.response.send_message("✅ TTS 종료 완료.", ephemeral=True)

    def build_settings_embed(self, settings: dict) -> discord.Embed:
        lang_label = next((k for k, v in LANG_CHOICES.items() if v == settings["lang"]), settings["lang"])
        speed_label = "느리게" if settings["slow"] else "보통"

        embed = discord.Embed(title="🔊 TTS 설정", color=discord.Color.blurple())
        embed.add_field(name="활성화", value="켜짐" if settings["enabled"] else "꺼짐", inline=True)
        embed.add_field(name="언어", value=lang_label, inline=True)
        embed.add_field(name="속도", value=speed_label, inline=True)
        embed.set_footer(text="입장하기를 누르면 현재 들어간 음성채널 기준으로 동작합니다.")
        return embed

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        guild = message.guild
        guild_id = guild.id
        settings = self.get_settings(guild_id)

        if not settings["enabled"]:
            return

        vc = guild.voice_client
        if vc is None or not vc.is_connected() or vc.channel is None:
            return

        # ✅ 네 원래 코드 방식 유지:
        # 음성채널 옆 채팅에서 온 메시지일 때만 읽기
        if message.channel.id != vc.channel.id:
            return

        text = message.content.strip()
        if not text:
            return

        if guild_id not in self.voice_queues:
            return

        text = text[:200]
        filename = os.path.join("tts_temp", f"{guild_id}_{uuid.uuid4().hex}.mp3")

        try:
            await self.generate_tts(text, settings["lang"], settings["slow"], filename)
        except Exception as e:
            print(f"[TTS 생성 오류] {e}")
            return

        await self.voice_queues[guild_id].put(filename)


class LanguageSelect(discord.ui.Select):
    def __init__(self, cog: TTSCog, guild_id: int):
        self.cog = cog
        self.guild_id = guild_id
        options = [discord.SelectOption(label=label, value=value) for label, value in LANG_CHOICES.items()]
        super().__init__(placeholder="언어 선택", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        settings = self.cog.get_settings(self.guild_id)
        settings["lang"] = self.values[0]
        embed = self.cog.build_settings_embed(settings)
        await interaction.response.edit_message(embed=embed, view=self.view)


class SpeedSelect(discord.ui.Select):
    def __init__(self, cog: TTSCog, guild_id: int):
        self.cog = cog
        self.guild_id = guild_id
        options = [discord.SelectOption(label=label, value=str(value)) for label, value in SPEED_CHOICES.items()]
        super().__init__(placeholder="속도 선택", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        settings = self.cog.get_settings(self.guild_id)
        settings["slow"] = (self.values[0] == "True")
        embed = self.cog.build_settings_embed(settings)
        await interaction.response.edit_message(embed=embed, view=self.view)


class JoinButton(discord.ui.Button):
    def __init__(self, cog: TTSCog, guild_id: int):
        super().__init__(label="입장하기", style=discord.ButtonStyle.success, emoji="🔊")
        self.cog = cog
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("서버에서만 사용 가능해요.", ephemeral=True)

        member = interaction.user
        if not isinstance(member, discord.Member) or member.voice is None or member.voice.channel is None:
            return await interaction.response.send_message("먼저 음성채널에 들어가 주세요.", ephemeral=True)

        guild = interaction.guild
        vc = guild.voice_client
        target = member.voice.channel

        try:
            if vc is None:
                vc = await target.connect()
            elif vc.channel != target:
                await vc.move_to(target)
        except Exception as e:
            return await interaction.response.send_message(f"입장 실패: {e}", ephemeral=True)

        if self.guild_id not in self.cog.voice_queues:
            self.cog.voice_queues[self.guild_id] = asyncio.Queue()

        if self.guild_id not in self.cog.voice_tasks or self.cog.voice_tasks[self.guild_id].done():
            self.cog.voice_tasks[self.guild_id] = self.cog.bot.loop.create_task(
                self.cog.process_voice_queue(self.guild_id, vc)
            )

        settings = self.cog.get_settings(self.guild_id)
        settings["enabled"] = True

        embed = self.cog.build_settings_embed(settings)
        await interaction.response.edit_message(embed=embed, view=self.view)


class LeaveButton(discord.ui.Button):
    def __init__(self, cog: TTSCog, guild_id: int):
        super().__init__(label="퇴장하기", style=discord.ButtonStyle.danger, emoji="👋")
        self.cog = cog
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("서버에서만 사용 가능해요.", ephemeral=True)

        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            await vc.disconnect()

        if self.guild_id in self.cog.voice_tasks:
            self.cog.voice_tasks[self.guild_id].cancel()
            del self.cog.voice_tasks[self.guild_id]
        if self.guild_id in self.cog.voice_queues:
            del self.cog.voice_queues[self.guild_id]

        settings = self.cog.get_settings(self.guild_id)
        settings["enabled"] = False

        embed = self.cog.build_settings_embed(settings)
        await interaction.response.edit_message(embed=embed, view=self.view)


class TTSSettingsView(discord.ui.View):
    def __init__(self, cog: TTSCog, guild_id: int):
        super().__init__(timeout=180)
        self.add_item(LanguageSelect(cog, guild_id))
        self.add_item(SpeedSelect(cog, guild_id))
        self.add_item(JoinButton(cog, guild_id))
        self.add_item(LeaveButton(cog, guild_id))


async def setup(bot: commands.Bot):
    await bot.add_cog(TTSCog(bot))