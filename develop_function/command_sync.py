"""
Sync Command Cog (prefix 버전)
----------------
봇 소유자가 필요할 때만 수동으로 슬래시 커맨드를 동기화하는 prefix 명령어.
- -동기화        : 모든 서버(글로벌)에 동기화, 반영까지 최대 1시간 걸릴 수 있음
- -동기화즉시    : 명령어를 실행한 서버에만 즉시 동기화 (개발/테스트용)

on_ready에서 매번 자동으로 sync()를 부르면 재연결마다 반복 호출돼서
레이트리밋 위험이 있으므로, 이렇게 명령어로 필요할 때만 실행하는 게 안전하다.
"""
import discord
from discord.ext import commands


class SyncCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="동기화")
    @commands.is_owner()
    async def sync_global(self, ctx: commands.Context):
        msg = await ctx.send("🔄 글로벌 동기화 중...\n시간이 다소 소요될 수 있어요.")
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

    @sync_global.error
    @sync_here.error
    async def sync_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("봇 소유자만 사용할 수 있어요.")
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCommands(bot))