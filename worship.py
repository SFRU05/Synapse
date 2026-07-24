import discord
from discord import app_commands
from discord.ext import commands


# ---------------- 숭배 버튼 View ----------------
class WorshipView(discord.ui.View):
    def __init__(self, initial_user: discord.User):
        super().__init__(timeout=None)
        self.worshipers = [initial_user]

    @discord.ui.button(label="숭배하기", style=discord.ButtonStyle.primary, emoji="🙏")
    async def worship_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 이미 숭배한 유저 체크
        if interaction.user in self.worshipers:
            await interaction.response.send_message("이미 숭배에 참여하셨어요!", ephemeral=True)
            return

        # 신도 목록 추가
        self.worshipers.append(interaction.user)
        worshipers_text = "\n".join([user.mention for user in self.worshipers])

        # 기존 Embed의 '당신을 따르는 신도자' 필드 업데이트
        embed = interaction.message.embeds[0]
        embed.set_field_at(
            index=0,
            name="당신을 따르는 신도자",
            value=worshipers_text,
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)


# ---------------- 등록 함수 (청소 코드 포맷과 동일) ----------------
def setup_worship(bot: commands.Bot):

    @bot.tree.context_menu(name="숭배하기")
    async def worship_user(interaction: discord.Interaction, user: discord.User):
        # 본인 숭배 방지
        if interaction.user.id == user.id:
            await interaction.response.send_message("❌ 자신을 숭배할 수는 없어요!", ephemeral=True)
            return

        first_worshiper = interaction.user

        embed = discord.Embed(
            title="✨ 대 숭 배 ✨",
            description=f"**{user.mention}** 님을 향한 숭배가 시작되었습니다!",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="당신을 따르는 신도자",
            value=first_worshiper.mention,
            inline=False
        )

        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)

        view = WorshipView(initial_user=first_worshiper)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)