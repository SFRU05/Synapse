import discord
from discord.ext import commands
import asyncio

bot = commands.Bot(command_prefix="-", intents=discord.Intents.all())
async def setup_ban_command(bot):
    @bot.command()
    @commands.has_permissions(ban_members=True)
    async def ban(ctx, member: discord.Member = None, *, reason: str = "사유 없음"):
        if member is None:
            await ctx.send("차단할 사용자를 멘션하거나 ID를 입력하세요.")
            return

        embed = discord.Embed(
            title="차단 확인",
            description=f"{member.mention} 님을 서버에서 차단하시겠습니까?",
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
                    await member.ban(reason=reason)
                    await confirm_message.clear_reactions()

                    embed = discord.Embed(
                        title="차단 완료",
                        description=f"{member.mention} 님이 서버에서 차단되었습니다.",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="사유", value=reason, inline=False)
                    embed.add_field(name="중재자", value=f"{ctx.author.mention}", inline=False)

                    await ctx.send(embed=embed)
                except discord.Forbidden:
                    await confirm_message.edit(content="봇에 적절한 권한이 없습니다.")
                except discord.HTTPException:
                    await confirm_message.edit(content="밴 요청을 처리하는 중 오류가 발생했습니다.")
            elif str(reaction.emoji) == "❌":
                await confirm_message.clear_reactions()

                embed = discord.Embed(
                    title="차단 요청 취소",
                    description="차단 요청이 취소되었습니다.",
                    color=discord.Color.light_gray()
                )
                await confirm_message.edit(embed=embed)
        except asyncio.TimeoutError:

            embed = discord.Embed(
                title="시간 초과",
                description="차단 요청이 취소되었습니다.",
                color=discord.Color.light_gray()
            )

            await confirm_message.clear_reactions()
            await confirm_message.edit(embed=embed)

    @ban.error
    async def ban_error(ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("올바르지 않은 사용자입니다. 다시 확인해주세요.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("이 명령어를 실행할 권한이 없습니다.")
        else:
            await ctx.send("명령어 실행 중 오류가 발생했습니다.")