import discord
from discord.ext import commands


class SyncCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="동기화")
    @commands.is_owner()
    async def sync_global(self, ctx: commands.Context):
        msg = await ctx.send("🔄 글로벌 동기화 중...")
        synced = await self.bot.tree.sync()

        names = ", ".join(f"`/{cmd.name}`" for cmd in synced) or "(없음)"
        if len(names) > 1000:
            names = names[:1000] + " ..."
        embed = discord.Embed(
            title="✅ 글로벌 동기화 완료",
            description=f"총 **{len(synced)}개** 명령어 동기화됨\n(디스코드 전체 반영까지 최대 1시간 정도 걸릴 수 있어요)",
            color=discord.Color.green(),
        )
        embed.add_field(name="명령어 목록", value=names, inline=False)
        await msg.edit(content=None, embed=embed)

    @commands.command(name="동기화즉시")
    @commands.is_owner()
    async def sync_here(self, ctx: commands.Context):
        if ctx.guild is None:
            await ctx.send("서버 안에서만 사용할 수 있어요.")
            return

        msg = await ctx.send("🔄 이 서버에 즉시 동기화 중...")
        guild = discord.Object(id=ctx.guild.id)
        self.bot.tree.copy_global_to(guild=guild)
        synced = await self.bot.tree.sync(guild=guild)

        names = ", ".join(f"`/{cmd.name}`" for cmd in synced) or "(없음)"
        if len(names) > 1000:
            names = names[:1000] + " ..."
        embed = discord.Embed(
            title="✅ 이 서버에 즉시 동기화 완료",
            description=f"총 **{len(synced)}개** 명령어 동기화됨",
            color=discord.Color.green(),
        )
        embed.add_field(name="명령어 목록", value=names, inline=False)
        await msg.edit(content=None, embed=embed)

    @commands.command(name="전체동기화")
    @commands.is_owner()
    async def sync_all_guilds(self, ctx: commands.Context):
        """봇이 들어가있는 모든 서버 ID를 자동으로 불러와서 하나씩 즉시 동기화"""
        msg = await ctx.send(f"🔄 총 {len(self.bot.guilds)}개 서버에 순차적으로 동기화 중...")

        success = 0
        failed = []
        for guild in self.bot.guilds:
            try:
                self.bot.tree.copy_global_to(guild=guild)
                await self.bot.tree.sync(guild=guild)
                success += 1
            except discord.HTTPException as e:
                failed.append(f"{guild.name} ({guild.id}): {e}")

        embed = discord.Embed(
            title="✅ 전체 서버 동기화 완료",
            description=f"성공: **{success}**개 / 전체: **{len(self.bot.guilds)}**개",
            color=discord.Color.green() if not failed else discord.Color.orange(),
        )
        if failed:
            fail_text = "\n".join(failed[:10])
            if len(failed) > 10:
                fail_text += f"\n... 외 {len(failed) - 10}개"
            embed.add_field(name="⚠️ 실패한 서버", value=fail_text, inline=False)

        await msg.edit(content=None, embed=embed)

    @commands.command(name="길드명령어초기화")
    @commands.is_owner()
    async def clear_all_guild_commands(self, ctx: commands.Context):
        """모든 서버의 '길드 전용' 명령어 등록을 지워서 중복 표시 문제를 정리한다.
        (글로벌 명령어는 그대로 남아있고, 각 서버는 글로벌 명령어만 보게 됨)"""
        msg = await ctx.send(f"🧹 총 {len(self.bot.guilds)}개 서버의 길드 전용 명령어 정리 중...")

        cleared = 0
        for guild in self.bot.guilds:
            self.bot.tree.clear_commands(guild=guild)
            await self.bot.tree.sync(guild=guild)
            cleared += 1

        await msg.edit(content=f"✅ {cleared}개 서버의 길드 전용 명령어를 정리했어요. (글로벌 명령어만 남음)")

    @sync_global.error
    @sync_here.error
    @sync_all_guilds.error
    @clear_all_guild_commands.error
    async def sync_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("봇 소유자만 사용할 수 있어요.")
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCommands(bot))