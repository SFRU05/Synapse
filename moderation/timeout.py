import discord
from discord import app_commands
from datetime import timedelta

class TimeoutConfirmView(discord.ui.View):
    def __init__(self, member: discord.Member, duration: int, reason: str, moderator: discord.Member):
        super().__init__(timeout=15)
        self.member = member
        self.duration = duration
        self.reason = reason
        self.moderator = moderator
        self.result = None

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.moderator.id

    @discord.ui.button(label="✅ 예", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction):
        self.result = "confirm"
        self.stop()
        await interaction.response.defer(ephemeral=False)

    @discord.ui.button(label="❌ 아니요", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction):
        self.result = "cancel"
        self.stop()
        await interaction.response.defer(ephemeral=True)

class PardonConfirmView(discord.ui.View):
    def __init__(self, member: discord.Member, moderator: discord.Member):
        super().__init__(timeout=15)
        self.member = member
        self.moderator = moderator
        self.result = None

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.moderator.id

    @discord.ui.button(label="✅ 예", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction):
        self.result = "confirm"
        self.stop()
        await interaction.response.defer(ephemeral=False)

    @discord.ui.button(label="❌ 아니요", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction):
        self.result = "cancel"
        self.stop()
        await interaction.response.defer(ephemeral=True)

@app_commands.command(name="타임아웃", description="유저를 일정 시간(분) 타임아웃합니다. (확인 버튼)")
@app_commands.describe(
    member="타임아웃할 멤버를 선택하세요.",
    duration="타임아웃 시간(분)",
    reason="사유. 기본값: 사유 없음"
)
async def timeout_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    duration: int,
    reason: str = "사유 없음"
):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
        return
    if duration <= 0:
        await interaction.response.send_message("타임아웃 시간(분)은 1 이상이어야 합니다.", ephemeral=True)
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
    embed.set_footer(text="15초 내 [예] 또는 [아니요]를 눌러주세요.")

    view = TimeoutConfirmView(member, duration, reason, interaction.user)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    await view.wait()

    if view.result == "confirm":
        try:
            await member.timeout(timeout_duration, reason=reason)
            public_embed = discord.Embed(
                title="타임아웃 완료",
                description=f"{member.mention} 님이 {int(hours)}시간 {int(minutes)}분 동안 타임아웃되었습니다.",
                color=discord.Color.green()
            )
            public_embed.add_field(name="중재자", value=interaction.user.mention, inline=True)
            public_embed.add_field(name="사유", value=reason, inline=False)
            await interaction.channel.send(embed=public_embed)  # 공개
            await interaction.edit_original_response(content="✅ 타임아웃이 수행되었습니다.", embed=None, view=None)
        except discord.Forbidden:
            await interaction.edit_original_response(content="❌ 봇에 타임아웃 권한이 없습니다.", embed=None, view=None)
        except discord.HTTPException:
            await interaction.edit_original_response(content="❌ 타임아웃 요청 중 오류가 발생했습니다.", embed=None, view=None)
    elif view.result == "cancel":
        cancel_embed = discord.Embed(
            title="타임아웃 요청 취소",
            description=f"{member.mention} 님에 대한 타임아웃 요청이 취소되었습니다.",
            color=discord.Color.light_grey()
        )
        await interaction.edit_original_response(embed=cancel_embed, view=None)
    else:
        timeout_embed = discord.Embed(
            title="시간 초과",
            description="15초 내 선택이 없어 타임아웃 요청이 취소되었습니다.",
            color=discord.Color.light_grey()
        )
        await interaction.edit_original_response(embed=timeout_embed, view=None)

@app_commands.command(name="pardon", description="유저의 타임아웃을 해제합니다. (확인 버튼)")
@app_commands.describe(
    member="타임아웃을 해제할 멤버를 선택하세요.",
)
async def pardon_slash(
    interaction: discord.Interaction,
    member: discord.Member
):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
        return

    embed = discord.Embed(
        title="타임아웃 해제 확인",
        description=f"{member.mention} 님의 타임아웃을 해제하시겠습니까?",
        color=discord.Color.orange()
    )
    embed.set_footer(text="15초 내 [예] 또는 [아니요]를 눌러주세요.")

    view = PardonConfirmView(member, interaction.user)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    await view.wait()

    if view.result == "confirm":
        try:
            await member.timeout(None)
            public_embed = discord.Embed(
                title="타임아웃 해제 완료",
                description=f"{member.mention} 님의 타임아웃이 해제되었습니다.",
                color=discord.Color.green()
            )
            public_embed.add_field(name="중재자", value=interaction.user.mention, inline=False)
            await interaction.channel.send(embed=public_embed)
            await interaction.edit_original_response(content="✅ 타임아웃 해제가 수행되었습니다.", embed=None, view=None)
        except discord.Forbidden:
            await interaction.edit_original_response(content="❌ 봇에 타임아웃 해제 권한이 없습니다.", embed=None, view=None)
        except discord.HTTPException:
            await interaction.edit_original_response(content="❌ 타임아웃 해제 요청 중 오류가 발생했습니다.", embed=None, view=None)
    elif view.result == "cancel":
        cancel_embed = discord.Embed(
            title="타임아웃 해제 요청 취소",
            description=f"{member.mention} 님에 대한 타임아웃 해제 요청이 취소되었습니다.",
            color=discord.Color.light_grey()
        )
        await interaction.edit_original_response(embed=cancel_embed, view=None)
    else:
        timeout_embed = discord.Embed(
            title="시간 초과",
            description="15초 내 선택이 없어 타임아웃 해제 요청이 취소되었습니다.",
            color=discord.Color.light_grey()
        )
        await interaction.edit_original_response(embed=timeout_embed, view=None)