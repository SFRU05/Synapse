import discord
from discord import app_commands
from logger_db import set_log_channel


@app_commands.command(name="로그 채널 설정", description="서버 로그용 채널을 지정합니다 (관리자만 가능)")
@app_commands.describe(channel="로그를 보낼 텍스트 채널")
async def setlog_slash(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("관리자 권한이 필요합니다.", ephemeral=True)
        return

    set_log_channel(interaction.guild.id, channel.id)
    embed = discord.Embed(
        title="로그 채널 설정 완료",
        description=f"{channel.mention} 채널이 로그 채널로 지정되었습니다.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)