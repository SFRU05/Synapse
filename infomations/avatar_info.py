import discord
from discord import app_commands
import datetime

@app_commands.command(name="아바타", description="사용자 아바타를 보여줍니다.")
@app_commands.describe(member="조회할 멤버를 선택하세요. (선택하지 않으면 자신의 아바타가 표시됩니다.)")
async def avatar_slash(
    interaction: discord.Interaction,
    member: discord.Member = None
):
    target = member or interaction.user
    embed = discord.Embed(
        title=f"{target.display_name}의 아바타",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now()
    )
    avatar_url = target.display_avatar.url if target.display_avatar else None
    embed.set_image(url=avatar_url)
    await interaction.response.send_message(embed=embed)