from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

DATA_FILE = Path(__file__).with_name("voice_channels_data.json")

ANIME_CHARACTER_NAMES = [
    # 악역 영애이기 때문에 최종 보스를 길러보았습니다
    "아이린", "클로드", "세드릭",
    "키스 엘포드", "벨제뷔트", "릴리아",

    # 여성향 게임의 파멸 플래그밖에 없는 악역 영애로 환생해버렸다…
    "카타리나 클라에스", "키스 클라에스", "지오르도 스티아트",
    "앨런 스티아트", "니콜 아스카르트", "메리 헌트",
    "소피아 아스카르트", "마리아 캠벨", "시리우스 디크",
    "라파엘 월터",

    # 악역 영애 레벨 99
    "유미엘라 돌크네스", "패트릭 애시배튼",
    "앨리시아 엔라이트", "에드윈 발샤인", "윌리엄 아레스",
    "오즈월드 그레이엄",

    # 악역 영애 전생 아저씨
    "그레이스 오베르뉴",
    "버지니아", "안나",

    # 전생 악녀의 흑역사
    "이아나 마그놀리아", "키리오 라이트",
    "솔 네모필라", "샤논 네모필라",

    # 전생했더니 악역 영애였다
    "클레어 프랑수아", "레이 테일러",
    "미샤 유르", "세이나 아말리아",

    # 악역 영애물 및 여성향 판타지 계열
    "엘리제 드 클로렌스", "린덴 드 로마노프",
    "로제마인", "페르디난드", "빌프리트",
    "샤를로테", "투리", "에파",

    # 책벌레의 하극상
    "마인", "벤노", "루츠", "길", "프랑", "다무엘",

    # 약사의 혼잣말
    "마오마오", "진시", "가오슌", "리화",
    "교쿠요", "리슈", "아두오",

    # 성녀의 마력은 만능입니다
    "세이라", "알베르트 호크", "유리 드루베이스",
    "요한 발데크", "에르하르트 호크",

    # 악역 영애와 여성향 게임 판타지 캐릭터
    "엘레노아 샤를로트", "샤를로트 에반스",
    "아델 폰 아스카", "루이제", "에리카",
    "마리 앙투아네트", "프란츠", "오스카",

    # 공작 영애의 소양
    "아이리스 라나 아르메리아", "디미트리 아르메리아",
    "토리", "릴리", "베르나르",

    # 악역 영애와 왕족·귀족 캐릭터
    "레티시아 그린", "클로드", "윌리엄",
    "엘리자베스 미들포드", "세실리아 실비",
    "알렉산더", "레온하르트", "루카스",
    "에드워드", "루돌프",

    # 추가 캐릭터명
    "아나스타샤", "비올라", "샤를로트",
    "에밀리아", "엘리자베트", "마리",
    "로제", "클레멘티아", "루시아",
    "리젤로테", "프리실라", "세라피나",
    "크리스티나", "아멜리아", "엘레노아",
    "이사벨라", "카밀라", "베아트리체",
    "아델라이드", "마가렛",
]



class VoiceChannelCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = self._load_data()

    def _load_data(self) -> dict:
        if not DATA_FILE.exists():
            return {"guilds": {}}
        try:
            with DATA_FILE.open("r", encoding="utf-8") as fp:
                loaded = json.load(fp)
            if not isinstance(loaded, dict):
                raise ValueError("잘못된 데이터 형식")
            loaded.setdefault("guilds", {})
            return loaded
        except (OSError, json.JSONDecodeError, ValueError):
            print("[voice_channel] 데이터 파일을 읽지 못했습니다. 기본 설정으로 시작합니다.")
            return {"guilds": {}}

    def _save_data(self) -> None:
        temp_file = DATA_FILE.with_suffix(".tmp")
        with temp_file.open("w", encoding="utf-8") as fp:
            json.dump(self.data, fp, ensure_ascii=False, indent=2)
        temp_file.replace(DATA_FILE)

    def _guild_data(self, guild_id: int) -> dict:
        guilds = self.data.setdefault("guilds", {})
        return guilds.setdefault(str(guild_id), {
            "entry_channel_id": None,
            "managed_channels": {},
        })

    def _managed_channels(self, guild_id: int) -> dict:
        return self._guild_data(guild_id).setdefault("managed_channels", {})

    def _channel_owner(self, guild_id: int, channel_id: int) -> Optional[int]:
        info = self._managed_channels(guild_id).get(str(channel_id))
        return int(info["owner_id"]) if info and info.get("owner_id") else None

    def _is_managed(self, guild_id: int, channel_id: int) -> bool:
        return str(channel_id) in self._managed_channels(guild_id)

    async def _delete_managed_channel(self, channel: discord.VoiceChannel) -> None:
        channels = self._managed_channels(channel.guild.id)
        channels.pop(str(channel.id), None)
        self._save_data()
        try:
            await channel.delete(reason="음성채널이 비어 있어 자동 삭제")
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            print(f"[voice_channel] 채널 삭제 실패 ({channel.id}): {exc}")

    async def _create_personal_channel(
        self, member: discord.Member, entry_channel: discord.VoiceChannel
    ) -> Optional[discord.VoiceChannel]:
        guild = member.guild
        category = entry_channel.category
        bot_member = guild.me
        if bot_member is None:
            return None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True, connect=True
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                stream=True,
                use_voice_activation=True,
                manage_channels=True,
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                manage_channels=True,
                move_members=True,
            ),
        }

        try:
            channel = await guild.create_voice_channel(
                name=random.choice(ANIME_CHARACTER_NAMES),
                category=category,
                user_limit=0,
                overwrites=overwrites,
                reason=f"{member}님의 개인 음성 채널 생성",
            )
        except discord.HTTPException as exc:
            print(f"[voice_channel] 채널 생성 실패: {exc}")
            return None

        self._managed_channels(guild.id)[str(channel.id)] = {
            "owner_id": member.id,
            "created_by": member.id,
        }
        self._save_data()
        return channel

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return

        guild = member.guild
        config = self._guild_data(guild.id)
        entry_id = config.get("entry_channel_id")

        # 먼저 입장용 채널 진입을 처리합니다.
        if after.channel and entry_id and after.channel.id == int(entry_id):
            personal = await self._create_personal_channel(member, after.channel)
            if personal:
                try:
                    await member.move_to(personal, reason="음성채널로 이동")
                except (discord.Forbidden, discord.HTTPException):
                    if not personal.members:
                        await self._delete_managed_channel(personal)

        # 나간 채널이 관리 대상이고 비어 있으면 삭제합니다.
        if before.channel and before.channel.id != (after.channel.id if after.channel else None):
            old_channel = before.channel
            if self._is_managed(guild.id, old_channel.id) and not old_channel.members:
                await self._delete_managed_channel(old_channel)

    async def cog_load(self) -> None:
        self.bot.loop.create_task(self._cleanup_empty_channels())

    async def _cleanup_empty_channels(self) -> None:
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            channels = self._managed_channels(guild.id)
            for channel_id in list(channels.keys()):
                channel = guild.get_channel(int(channel_id))
                if not isinstance(channel, discord.VoiceChannel):
                    channels.pop(channel_id, None)
                elif not channel.members:
                    await self._delete_managed_channel(channel)
            self._save_data()

    async def _get_current_personal_channel(
        self, interaction: discord.Interaction
    ) -> Optional[discord.VoiceChannel]:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return None
        voice = interaction.user.voice
        if not voice or not isinstance(voice.channel, discord.VoiceChannel):
            return None
        channel = voice.channel
        if not self._is_managed(interaction.guild.id, channel.id):
            return None
        return channel

    async def _require_owner(
        self, interaction: discord.Interaction, channel: discord.VoiceChannel
    ) -> bool:
        owner_id = self._channel_owner(channel.guild.id, channel.id)
        if owner_id != interaction.user.id:
            await interaction.response.send_message(
                "이 기능은 해당 음성채널의 소유자만 사용할 수 있어요.",
                ephemeral=True,
            )
            return False
        return True

    @app_commands.command(name="채널생성설정", description="음성채널 자동 생성용 입장 채널을 설정합니다.")
    @app_commands.describe(채널="입장하면 음성채널이 만들어질 음성 채널")
    @app_commands.default_permissions(manage_guild=True)
    async def set_entry_channel(
        self, interaction: discord.Interaction, 채널: discord.VoiceChannel
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("서버에서만 사용할 수 있어요.", ephemeral=True)
            return
        config = self._guild_data(interaction.guild.id)
        config["entry_channel_id"] = 채널.id
        self._save_data()
        await interaction.response.send_message(
            f"설정 완료! {채널.mention}에 입장하면 개인 음성 채널이 생성돼요.",
            ephemeral=True,
        )

    @app_commands.command(name="음성채널", description="현재 개인 음성 채널의 관리 대시보드를 열어요.")
    async def voice_dashboard(self, interaction: discord.Interaction) -> None:
        channel = await self._get_current_personal_channel(interaction)
        if not channel:
            await interaction.response.send_message(
                "먼저 설정된 입장 채널을 통해 생성된 음성채널에 들어가 주세요.",
                ephemeral=True,
            )
            return

        owner_id = self._channel_owner(channel.guild.id, channel.id)
        owner = channel.guild.get_member(owner_id) if owner_id else None
        owner_text = owner.mention if owner else "알 수 없음"
        limit_text = str(channel.user_limit) if channel.user_limit else "제한 없음"

        embed = discord.Embed(
            title="🎙️ 음성채널 대시보드",
            color=discord.Color.blurple(),
            description="아래 버튼으로 음성 채널을 관리할 수 있어요.",
        )
        embed.add_field(name="채널 이름", value=channel.name, inline=True)
        embed.add_field(name="소유자", value=owner_text, inline=True)
        embed.add_field(
            name="현재 인원",
            value=f"{len(channel.members)}명 / {limit_text}",
            inline=True,
        )
        embed.add_field(
            name="채널 ID",
            value=f"`{channel.id}`",
            inline=False,
        )
        await interaction.response.send_message(
            embed=embed,
            view=VoiceDashboardView(self, channel.id),
            ephemeral=True,
        )


class RenameModal(discord.ui.Modal, title="음성채널 이름 변경"):
    new_name = discord.ui.TextInput(
        label="새 채널 이름",
        placeholder="최대 30자",
        min_length=1,
        max_length=30,
    )

    def __init__(self, cog: VoiceChannelCog, channel_id: int):
        super().__init__()
        self.cog = cog
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("채널을 찾을 수 없어요.", ephemeral=True)
            return
        if not await self.cog._require_owner(interaction, channel):
            return
        try:
            await channel.edit(name=str(self.new_name).strip(), reason="이름 변경")
        except discord.HTTPException:
            await interaction.response.send_message("이름 변경에 실패했어요.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"채널 이름을 **{channel.name}**(으)로 변경했어요.", ephemeral=True
        )


class UserLimitModal(discord.ui.Modal, title="음성채널 인원 제한"):
    limit = discord.ui.TextInput(
        label="최대 인원 (0~99, 0은 제한 없음)",
        placeholder="예: 5",
        min_length=1,
        max_length=2,
    )

    def __init__(self, cog: VoiceChannelCog, channel_id: int):
        super().__init__()
        self.cog = cog
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("채널을 찾을 수 없어요.", ephemeral=True)
            return
        if not await self.cog._require_owner(interaction, channel):
            return
        try:
            limit = int(str(self.limit))
        except ValueError:
            await interaction.response.send_message("숫자로 입력해 주세요.", ephemeral=True)
            return
        if not 0 <= limit <= 99:
            await interaction.response.send_message("0부터 99 사이의 숫자를 입력해 주세요.", ephemeral=True)
            return
        try:
            await channel.edit(user_limit=limit, reason="개인 채널 소유자 인원 제한 변경")
        except discord.HTTPException:
            await interaction.response.send_message("인원 제한 변경에 실패했어요.", ephemeral=True)
            return
        label = "제한 없음" if limit == 0 else f"{limit}명"
        await interaction.response.send_message(f"최대 인원을 **{label}**(으)로 설정했어요.", ephemeral=True)


class TransferSelect(discord.ui.Select):
    def __init__(self, cog: VoiceChannelCog, channel: discord.VoiceChannel):
        self.cog = cog
        self.channel_id = channel.id
        options = [
            discord.SelectOption(
                label=member.display_name[:100],
                value=str(member.id),
                description=f"@{member.name}"[:100],
            )
            for member in channel.members
            if not member.bot
        ][:25]
        super().__init__(
            placeholder="소유권을 넘길 멤버를 선택하세요",
            min_values=1,
            max_values=1,
            options=options,
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("채널을 찾을 수 없어요.", ephemeral=True)
            return
        if not await self.cog._require_owner(interaction, channel):
            return

        target_id = int(self.values[0])
        target = interaction.guild.get_member(target_id) if interaction.guild else None
        if not target or target not in channel.members or target.bot:
            await interaction.response.send_message(
                "선택한 멤버가 현재 채널에 없어요. 대시보드를 다시 열어 주세요.",
                ephemeral=True,
            )
            return

        old_owner = interaction.user
        overwrites = channel.overwrites
        old_overwrite = overwrites.get(old_owner, discord.PermissionOverwrite())
        old_overwrite.view_channel = True
        old_overwrite.connect = True
        # 이전 소유자의 디스코드 채널 관리 권한은 회수
        old_overwrite.manage_channels = False
        overwrites[old_owner] = old_overwrite

        new_overwrite = overwrites.get(target, discord.PermissionOverwrite())
        new_overwrite.view_channel = True
        new_overwrite.connect = True
        new_overwrite.speak = True
        new_overwrite.stream = True
        new_overwrite.use_voice_activation = True
        new_overwrite.manage_channels = True
        overwrites[target] = new_overwrite

        try:
            await channel.edit(overwrites=overwrites, reason="음성채널 소유권 양도")
        except discord.HTTPException:
            await interaction.response.send_message("권한 변경에 실패했어요.", ephemeral=True)
            return

        self.cog._managed_channels(channel.guild.id)[str(channel.id)]["owner_id"] = target.id
        self.cog._save_data()
        await interaction.response.send_message(
            f"✅ {target.mention}님에게 **{channel.name}** 채널의 소유권을 양도했어요.",
            ephemeral=True,
        )


class TransferView(discord.ui.View):
    def __init__(self, cog: VoiceChannelCog, channel: discord.VoiceChannel):
        super().__init__(timeout=120)
        self.add_item(TransferSelect(cog, channel))


class VoiceDashboardView(discord.ui.View):
    def __init__(self, cog: VoiceChannelCog, channel_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.channel_id = channel_id

    async def _channel_and_owner_check(
        self, interaction: discord.Interaction
    ) -> Optional[discord.VoiceChannel]:
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("채널이 이미 삭제되었어요.", ephemeral=True)
            return None
        if not await self.cog._require_owner(interaction, channel):
            return None
        return channel

    @discord.ui.button(label="이름 변경", style=discord.ButtonStyle.primary, emoji="✏️")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._channel_and_owner_check(interaction)
        if channel:
            await interaction.response.send_modal(RenameModal(self.cog, channel.id))

    @discord.ui.button(label="인원 제한", style=discord.ButtonStyle.secondary, emoji="👥")
    async def user_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._channel_and_owner_check(interaction)
        if channel:
            await interaction.response.send_modal(UserLimitModal(self.cog, channel.id))

    @discord.ui.button(label="권한 양도", style=discord.ButtonStyle.success, emoji="🔁")
    async def transfer(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._channel_and_owner_check(interaction)
        if not channel:
            return
        if not any(not member.bot and member.id != interaction.user.id for member in channel.members):
            await interaction.response.send_message(
                "소유권을 양도할 다른 멤버가 현재 채널에 없어요.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "소유권을 양도할 멤버를 선택해 주세요.",
            view=TransferView(self.cog, channel),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceChannelCog(bot))
