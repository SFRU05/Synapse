import discord
from discord.ext import commands
import sqlite3

# 개발자 ID 설정
DEVELOPER_IDS = [725694061998243850]


def is_developer_check(ctx):
    return ctx.author.id in DEVELOPER_IDS


# 드롭다운 및 버튼 UI 클래스들 (이전 코드와 동일)
class GuildActionSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        options = []
        for guild in bot.guilds[:25]:
            options.append(
                discord.SelectOption(
                    label=guild.name,
                    description=f"ID: {guild.id} | 멤버 수: {guild.member_count}명",
                    value=str(guild.id)
                )
            )
        if not options:
            options.append(discord.SelectOption(label="참여 중인 서버 없음", value="none"))

        super().__init__(placeholder="⚙️ 관리할 서버를 선택하세요...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message("❌ 개발자만 이 메뉴를 조작할 수 있습니다.", ephemeral=True)
            return
        guild_id_str = self.values[0]
        if guild_id_str == "none":
            await interaction.response.send_message("❌ 선택할 수 있는 서버가 없습니다.", ephemeral=True)
            return

        await interaction.response.send_message(
            content=f"선택된 서버 ID: `{guild_id_str}`\n수행할 작업을 선택해 주세요.",
            view=GuildActionButtons(interaction.client, int(guild_id_str)),
            ephemeral=True
        )


class GuildActionButtons(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="서버 조회", style=discord.ButtonStyle.blurple, emoji="📊")
    async def view_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            conn = sqlite3.connect("discord_logs.db")
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id FROM log_channels WHERE guild_id = ?", (self.guild_id,))
            log_channel = cursor.fetchone()
            cursor.execute("SELECT * FROM log_settings WHERE guild_id = ?", (self.guild_id,))
            log_settings = cursor.fetchone()
            conn.close()

            embed = discord.Embed(title="📊 서버 데이터 조회", description=f"서버 ID: `{self.guild_id}`",
                                  color=discord.Color.blurple())
            embed.add_field(name="📋 로그 채널", value=f"채널 ID: `{log_channel[0]}`" if log_channel else "설정되지 않음",
                            inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: `{str(e)}`", ephemeral=True)

    @discord.ui.button(label="데이터 삭제", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            conn = sqlite3.connect("discord_logs.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM log_channels WHERE guild_id = ?", (self.guild_id,))
            cursor.execute("DELETE FROM log_settings WHERE guild_id = ?", (self.guild_id,))
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            await interaction.followup.send(f"✅ 데이터 삭제 완료 (삭제된 행: {deleted_count}개)", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: `{str(e)}`", ephemeral=True)

    @discord.ui.button(label="서버 나가기", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def leave_guild_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.followup.send("❌ 봇이 서버를 찾을 수 없습니다.", ephemeral=True)
            return
        try:
            await guild.leave()
            await interaction.followup.send(f"✅ 서버에서 나갔습니다.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: `{str(e)}`", ephemeral=True)


class GuildSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=60)
        self.add_item(GuildActionSelect(bot))


# ==============================================================================
# 메인 파일에서 로드할 Cog 클래스 정의
# ==============================================================================
class DeveloperCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="개발")
    @commands.check(is_developer_check)
    async def developer_panel(self, ctx):
        embed = discord.Embed(
            title="🤖 개발자 전용 서버 제어판",
            description="하단의 드롭다운 메뉴에서 원하시는 서버를 관리해 주세요.",
            color=discord.Color.blurple()
        )
        total_users = sum(g.member_count for g in self.bot.guilds)
        embed.add_field(name="서버 수 / 총 유저 수", value=f"`{len(self.bot.guilds)}개` / `{total_users}명`", inline=True)
        embed.add_field(name="레이턴시", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)

        view = GuildSelectView(self.bot)
        await ctx.send(embed=embed, view=view)

    @developer_panel.error
    async def developer_panel_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 개발자만 사용 가능한 명령어입니다.")


# 💡 main.py에서 이 함수를 호출하여 명령어를 추가하게 됩니다.
async def setup(bot: commands.Bot):
    await bot.add_cog(DeveloperCommands(bot))