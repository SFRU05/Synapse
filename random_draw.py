import random
import discord
from discord.ext import commands
import asyncio
import datetime

class RandomDraw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_draw = None
        self.last_message = None
        self.last_author_id = None
        self.last_winners = []

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
        self.last_draw = (num_winners, names)
        self.last_message = None
        self.last_author_id = ctx.author.id
        self.last_winners = winners

        embed = discord.Embed(
            title="🎲 랜덤 추첨 결과",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="추첨 인원", value=", ".join(args[1:]), inline=False)
        embed.add_field(name="당첨자", value=", ".join(winners), inline=False)
        embed.set_footer(text="재추첨은 아래 이모지를 눌러주세요")
        self.last_draw = (num_winners, names)

        message = await ctx.send(embed=embed)
        self.last_message = message
        self.last_author_id = ctx.author.id
        await message.add_reaction("🔄")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return
        if (
                self.last_message
                and reaction.message.id == self.last_message.id
                and str(reaction.emoji) == "🔄"
                and user.id == self.last_author_id
                and self.last_draw is not None  # None 체크 추가
        ):
            await reaction.message.channel.send("🎲 재추첨 중입니다... ")
            await asyncio.sleep(3)

            num_winners, names = self.last_draw

            available_names = [n for n in names if n not in self.last_winners]
            if len(available_names) < num_winners:
                return

            winners = random.sample(available_names, num_winners)
            self.last_winners = winners
            embed = discord.Embed(
                title="🔄 재추첨 결과",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="추첨 인원", value=", ".join(names), inline=False)
            embed.add_field(name="당첨자", value=", ".join(winners), inline=False)
            await reaction.message.channel.send(embed=embed)

def setup(bot):
    bot.add_cog(RandomDraw(bot))