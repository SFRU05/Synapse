import discord
from discord.ext import commands
from datetime import timedelta
import asyncio

bot = commands.Bot(command_prefix="-", intents=discord.Intents.all())

async def setup_timeout_command(bot):
    @bot.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(ctx, member: discord.Member = None, duration: int = None, *, reason: str = "사유 없음"):
        if member is None:
            await ctx.send("타임아웃할 사용자를 멘션하거나 ID를 입력하세요.\n예: `-timeout <사용자> <시간(분)> [사유]`")
            return

        if duration is None or duration <= 0:
            await ctx.send("타임아웃 시간을 분 단위로 입력하세요.\n예: `-timeout <사용자> <시간(분)> [사유]`")
            return

        timeout_duration = timedelta(minutes=duration)
        hours, remainder = divmod(timeout_duration.total_seconds(), 3600)
        minutes = remainder // 60

        embed = discord.Embed(
            title="타임아웃 확인",
            description=f"{member.mention} 님을 {int(hours)}시간 {int(minutes)}분 동안 타임아웃하시겠습니까?",
            color=discord.Color.red()
        )
        embed.add_field(name="사유", value=reason, inline=False)

        confirm_message = await ctx.send(embed=embed)
        await confirm_message.add_reaction("✅")
        await confirm_message.add_reaction("❌")

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in ["✅", "❌"]
                and reaction.message.id == confirm_message.id
            )

        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=15.0, check=check)
            if str(reaction.emoji) == "✅":
                try:
                    await member.timeout(timeout_duration, reason=reason)

                    embed = discord.Embed(
                        title="타임아웃 완료",
                        description=f"{member.mention} 님이 타임아웃되었습니다.",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="기간", value=f"{int(hours)}시간 {int(minutes)}분", inline=True)
                    embed.add_field(name="중재자", value=f"{ctx.author.mention}", inline=True
                                    )
                    embed.add_field(name="사유", value=reason, inline=False)


                    await ctx.send(embed=embed)
                except discord.Forbidden:
                    await ctx.send("봇에 타임아웃 권한이 없습니다.")
                except discord.HTTPException:
                    await ctx.send("타임아웃 요청을 처리하는 중 오류가 발생했습니다.")
            elif str(reaction.emoji) == "❌":
                await confirm_message.clear_reactions()

                embed = discord.Embed(
                    title="타임아웃 요청 취소",
                    description="타임아웃 요청이 취소되었습니다.",
                    color=discord.Color.light_gray()
                )
                await confirm_message.edit(embed=embed)
        except asyncio.TimeoutError:
            await confirm_message.clear_reactions()

            embed = discord.Embed(
                title="시간 초과",
                description="타임아웃 요청이 취소되었습니다.",
                color=discord.Color.light_gray()
            )
            await confirm_message.edit(embed=embed)

    @timeout.error
    async def timeout_error(ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("올바르지 않은 사용자입니다. 다시 확인해주세요.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("이 명령어를 실행할 권한이 없습니다.")
        else:
            await ctx.send("명령어 실행 중 오류가 발생했습니다.")

async def pardon_timeout(bot):
    @bot.command()
    @commands.has_permissions(moderate_members=True)
    async def pardon(ctx, member: discord.Member = None):
        if member is None:
            await ctx.send("타임아웃을 해제할 사용자를 멘션하거나 ID를 입력하세요.\n예: `-pardon <사용자>`")
            return

        try:
            await member.timeout(None)

            embed = discord.Embed(
                title="타임아웃 해제 완료",
                description=f"{member.mention} 님의 타임아웃이 해제되었습니다.",
                color=discord.Color.green()
            )
            embed.add_field(name="중재자", value=f"{ctx.author.mention}", inline=False)

            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("봇에 타임아웃 해제 권한이 없습니다.")
        except discord.HTTPException:
            await ctx.send("타임아웃 해제 요청을 처리하는 중 오류가 발생했습니다.")

    @pardon.error
    async def remove_timeout_error(ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("올바르지 않은 사용자입니다. 다시 확인해주세요.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("이 명령어를 실행할 권한이 없습니다.")
        else:
            await ctx.send("명령어 실행 중 오류가 발생했습니다.")