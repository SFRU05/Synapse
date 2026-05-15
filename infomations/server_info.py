import discord
from discord import app_commands
import datetime

@app_commands.command(name="서버 정보", description="이 서버의 정보를 보여줍니다.")
async def serverinfo_slash(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("서버 정보는 서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"{guild.name} 서버 정보",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.UTC)
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="서버 이름", value=guild.name, inline=True)
    embed.add_field(name="서버 ID", value=guild.id, inline=True)
    embed.add_field(name="소유자", value=guild.owner.mention if guild.owner else "알 수 없음", inline=True)
    embed.add_field(name="멤버 수", value=f"{guild.member_count}명", inline=True)
    embed.add_field(
        name="생성일",
        value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        inline=True
    )
    await interaction.response.send_message(embed=embed)