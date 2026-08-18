import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from leveling.utils.database import LevelDB
from leveling.utils.rank_card import generate_rank_card


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = LevelDB()
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        await self.db.init()
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is None:
            return  # DM 제외

        result = await self.db.record_message(message.author.id, message.guild.id)

        if result["leveled_up"]:
            try:
                # message.channel.send 대신 message.author.send 사용
                await message.author.send(
                    f"🎉 **{message.guild.name}** 서버에서 **레벨 {result['level']}**(으)로 레벨업했어요!"
                )
            except discord.Forbidden:
                # 유저가 서버 멤버의 DM 수신을 거부해둔 경우 발생
                pass

    @app_commands.command(name="레벨", description="채팅량 기반 레벨 카드를 확인해요.")
    @app_commands.describe(유저="레벨을 확인할 유저 (비워두면 본인을 확인해요)")
    async def level(self, interaction: discord.Interaction, 유저: discord.Member | None = None):
        target = 유저 or interaction.user
        await interaction.response.defer()

        stats = await self.db.get_stats(target.id, interaction.guild_id)

        avatar_asset = target.display_avatar.replace(size=256, format="png")
        async with self.session.get(str(avatar_asset.url)) as resp:
            avatar_bytes = await resp.read()

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
        )

        file = discord.File(buf, filename="rank_card.png")
        await interaction.followup.send(file=file)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
