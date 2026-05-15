import discord
from discord import app_commands

class KickConfirmView(discord.ui.View):
    def __init__(self, member: discord.Member, reason: str, moderator: discord.Member):
        super().__init__(timeout=15)
        self.member = member
        self.reason = reason
        self.moderator = moderator
        self.result = None

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.moderator.id

    @discord.ui.button(label="✅ 예", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = "confirm"
        self.stop()
        await interaction.response.defer(ephemeral=False)

    @discord.ui.button(label="❌ 아니요", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = "cancel"
        self.stop()
        await interaction.response.defer(ephemeral=True)

@app_commands.command(name="추방", description="멤버를 추방합니다. (확인 버튼)")
@app_commands.describe(
    member="추방할 멤버를 선택하세요.",
    reason="추방 사유. 기본값: 사유 없음"
)
async def kick_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "사유 없음"
):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("이 명령어를 실행할 권한이 없습니다.", ephemeral=True)
        return
    if member is None:
        await interaction.response.send_message("추방할 멤버를 선택하세요.", ephemeral=True)
        return
    if member == interaction.user:
        await interaction.response.send_message("자기 자신은 추방할 수 없습니다.", ephemeral=True)
        return

    embed = discord.Embed(
        title="추방 확인",
        description=f"{member.mention} 님을 추방하시겠습니까?",
        color=discord.Color.red()
    )
    embed.add_field(name="사유", value=reason, inline=False)
    embed.set_footer(text="15초 내 [예] 또는 [아니요]를 눌러주세요.")

    view = KickConfirmView(member, reason, interaction.user)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    await view.wait()

    if view.result == "confirm":
        try:
            await member.kick(reason=reason)
            public_embed = discord.Embed(
                title="추방 완료",
                description=f"{member.mention} 님이 추방되었습니다.",
                color=discord.Color.green()
            )
            public_embed.add_field(name="사유", value=reason, inline=False)
            public_embed.add_field(name="중재자", value=interaction.user.mention, inline=False)

            await interaction.channel.send(embed=public_embed)
            await interaction.edit_original_response(content="✅ 추방이 수행되었습니다.", embed=None, view=None)
        except discord.Forbidden:
            await interaction.edit_original_response(content="❌ 봇에 추방 권한이 없습니다.", embed=None, view=None)
        except discord.HTTPException:
            await interaction.edit_original_response(content="❌ 추방 요청 중 오류가 발생했습니다.", embed=None, view=None)
    elif view.result == "cancel":
        cancel_embed = discord.Embed(
            title="추방 요청 취소",
            description="추방 요청이 취소되었습니다.",
            color=discord.Color.light_grey()
        )
        await interaction.edit_original_response(embed=cancel_embed, view=None)
    else:
        timeout_embed = discord.Embed(
            title="시간 초과",
            description="15초 내 선택이 없어 추방 요청이 취소되었습니다.",
            color=discord.Color.light_grey()
        )
        await interaction.edit_original_response(embed=timeout_embed, view=None)