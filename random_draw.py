import random
import discord
from discord.ext import commands
import time
import asyncio
import datetime

class RandomDraw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def draw(self, ctx):
        args = ctx.message.content.split()[1:]
        if not args or not args[0].isdigit():
            await ctx.send("사용법: `-draw 당첨인원 이름1 이름2 ...`")
            return

        num_winners = int(args[0])
        names = args[1:]

        if num_winners < 1 or num_winners > len(names):
            await ctx.send("당첨 인원은 참가자 수보다 많을 수 없습니다.")
            return

        await ctx.send("🎲 추첨 중입니다... ")
        await asyncio.sleep(3)

        winners = random.sample(names, num_winners)
        embed = discord.Embed(
            title="🎲 랜덤 추첨 결과",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="추첨 인원", value=", ".join(args[1:]), inline=False)
        embed.add_field(name="당첨자", value=", ".join(winners), inline=False)
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(RandomDraw(bot))