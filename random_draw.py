import random
import discord
from discord.ext import commands
from discord import app_commands
import datetime

class RerollView(discord.ui.View):
    def __init__(self, names, num_winners, orig_user):
        super().__init__(timeout=180)
        self.names = names
        self.num_winners = num_winners
        self.orig_user = orig_user
        self.last_winners = []

    @discord.ui.button(label="🔄 재추첨", style=discord.ButtonStyle.primary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):   # <--- button 추가!
        if interaction.user.id != self.orig_user.id:
            await interaction.response.send_message("재추첨은 추첨 시작자만 사용할 수 있습니다!", ephemeral=True)
            return
        # 동일 당첨자 재방지: 전부 과거 당첨자면 전체 풀로 롤링
        available = [n for n in self.names if n not in self.last_winners]
        if len(available) < self.num_winners:
            available = self.names
        winners = random.sample(available, self.num_winners)
        self.last_winners = winners
        embed = discord.Embed(
            title="🔄 재추첨 결과",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="추첨 인원", value=", ".join(self.names), inline=False)
        embed.add_field(name="당첨자", value=", ".join(winners), inline=False)
        await interaction.response.send_message(embed=embed)

class RandomDraw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="추첨", description="참가자 중 n명 랜덤 추첨")
    @app_commands.describe(
        num_winners="당첨 인원수 (정수, 참가자 명수 이하)",
        names="참가자 이름들 (쉼표, 띄어쓰기, 슬래시 등으로 구분 가능)"
    )
    async def draw(
        self,
        interaction: discord.Interaction,
        num_winners: int,
        names: str,
    ):
        # 참가자 이름 나누기 (쉼표, /, 공백 등)
        name_list = [
            n.strip()
            for n in names.replace("/", ",").replace(" ", ",").split(",")
            if n.strip()
        ]
        if not name_list or num_winners < 1:
            await interaction.response.send_message(
                "사용법: `/draw 당첨인원수 참가자1,참가자2,...`", ephemeral=True)
            return
        if num_winners > len(name_list):
            await interaction.response.send_message(
                "당첨 인원은 참가자 수보다 많을 수 없습니다.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        winners = random.sample(name_list, num_winners)
        view = RerollView(name_list, num_winners, interaction.user)
        view.last_winners = winners

        embed = discord.Embed(
            title="🎲 랜덤 추첨 결과",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="추첨 인원", value=", ".join(name_list), inline=False)
        embed.add_field(name="당첨자", value=", ".join(winners), inline=False)
        embed.set_footer(text="재추첨은 아래 버튼을 눌러주세요")
        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(RandomDraw(bot))