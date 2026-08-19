import os
import json
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from leveling.utils.database import LevelDB
from leveling.utils.rank_card import generate_rank_card
from leveling.utils.leaderboard_card import generate_leaderboard_card

SETTINGS_FILE = "data/notification_settings.json"


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = LevelDB()
        self.session: aiohttp.ClientSession | None = None
        self.notif_settings: dict[str, bool] = self.load_settings()

    def load_settings(self) -> dict[str, bool]:
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_settings(self):
        """현재 알림 설정을 JSON 파일에 저장합니다."""
        folder = os.path.dirname(SETTINGS_FILE)
        if folder:
            os.makedirs(folder, exist_ok=True)

        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.notif_settings, f, ensure_ascii=False, indent=4)

    async def cog_load(self):
        await self.db.init()
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    # ---------------------------------------------------------
    # 공용 헬퍼
    # ---------------------------------------------------------
    async def _fetch_bytes(self, url: str) -> bytes:
        async with self.session.get(url) as resp:
            return await resp.read()

    async def _guild_icon_bytes(self, guild: discord.Guild | None) -> bytes | None:
        if guild and guild.icon:
            return await self._fetch_bytes(str(guild.icon.replace(size=128, format="png").url))
        return None

    async def _resolve_member_entry(self, guild: discord.Guild, entry: dict, my_id: int) -> dict:
        """DB에서 나온 {user_id, weekly_count, level, exp, rank} 에 실제 유저 정보(이름/아바타)를 채워 넣는다."""
        uid = int(entry["user_id"])
        member = guild.get_member(uid)
        if member is None:
            try:
                member = await guild.fetch_member(uid)
            except discord.NotFound:
                member = None

        if member:
            name = member.display_name
            avatar_bytes = await self._fetch_bytes(
                str(member.display_avatar.replace(size=128, format="png").url)
            )
        else:
            name = "알 수 없는 유저"
            avatar_bytes = None

        return {
            **entry,
            "name": name,
            "avatar_bytes": avatar_bytes,
            "is_me": (uid == my_id),
        }

    # ---------------------------------------------------------
    # 메시지 감지 -> 채팅량 기록 + exp 지급 + (설정 시) DM 레벨업 알림
    # ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is None:
            return  # DM 제외

        result = await self.db.record_message(message.author.id, message.guild.id)

        if result["leveled_up"]:
            user_id = str(message.author.id)
            # 기본값은 False(꺼짐)
            if self.notif_settings.get(user_id, False):
                try:
                    await message.author.send(
                        f"🎉 **{message.guild.name}** 서버에서 **레벨 {result['level']}**(으)로 레벨업했어요!"
                    )
                except discord.Forbidden:
                    pass

    # ---------------------------------------------------------
    # /레벨 명령어
    # ---------------------------------------------------------
    @app_commands.command(name="레벨", description="채팅량 기반 레벨 카드를 확인해요.")
    @app_commands.describe(유저="레벨을 확인할 유저 (비워두면 본인을 확인해요)")
    async def level(self, interaction: discord.Interaction, 유저: discord.Member | None = None):
        target = 유저 or interaction.user
        await interaction.response.defer()

        stats = await self.db.get_stats(target.id, interaction.guild_id)
        avatar_bytes = await self._fetch_bytes(
            str(target.display_avatar.replace(size=256, format="png").url)
        )
        guild = interaction.guild
        guild_icon_bytes = await self._guild_icon_bytes(guild)

        buf = generate_rank_card(
            display_name=target.display_name,
            avatar_bytes=avatar_bytes,
            level=stats["level"],
            exp=stats["exp"],
            need=stats["need"],
            total_messages=stats["total_messages"],
            today_count=stats["today_count"],
            week_total=stats["week_total"],
            weekly=stats["weekly"],
            guild_name=guild.name if guild else None,
            guild_icon_bytes=guild_icon_bytes,
        )

        file = discord.File(buf, filename="rank_card.png")
        await interaction.followup.send(file=file)

    # ---------------------------------------------------------
    # /순위 명령어
    # ---------------------------------------------------------
    @app_commands.command(name="순위", description="이번 주 채팅 랭킹 TOP 10과 내 순위를 확인해요.")
    async def leaderboard(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("서버 안에서만 사용할 수 있어요.", ephemeral=True)
            return

        await interaction.response.defer()

        data = await self.db.get_weekly_leaderboard(guild.id, interaction.user.id, top_n=10)

        top_resolved = [
            await self._resolve_member_entry(guild, e, interaction.user.id) for e in data["top"]
        ]
        my_in_top = any(e["is_me"] for e in top_resolved)
        my_resolved = await self._resolve_member_entry(guild, data["me"], interaction.user.id)

        guild_icon_bytes = await self._guild_icon_bytes(guild)

        buf = generate_leaderboard_card(
            guild_name=guild.name,
            guild_icon_bytes=guild_icon_bytes,
            top_entries=top_resolved,
            my_entry=my_resolved,
            my_in_top=my_in_top,
        )

        file = discord.File(buf, filename="leaderboard.png")
        await interaction.followup.send(file=file)

    # ---------------------------------------------------------
    # /레벨알림 명령어
    # ---------------------------------------------------------
    @app_commands.command(name="레벨알림", description="레벨업 시 DM으로 알림을 받을지 여부를 설정해요.")
    async def toggle_notification(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        # 현재 상태 반전 (없으면 기본값 False였으므로 True로 변경)
        current_state = self.notif_settings.get(user_id, False)
        new_state = not current_state

        self.notif_settings[user_id] = new_state
        self.save_settings()

        if new_state:
            await interaction.response.send_message(
                "🔔 레벨업 DM 알림이 **활성화됐어요**. 이제 레벨업 시 DM을 발송해드려요.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "🔕 레벨업 DM 알림이 **비활성화됐어요**.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))