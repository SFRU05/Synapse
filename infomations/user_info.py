import discord
from discord import app_commands

@app_commands.command(name="유저정보", description="사용자(자신/다른 유저)의 정보를 보여줍니다.")
@app_commands.describe(member="정보를 확인할 멤버 (생략시 본인)")
async def userinfo_slash(
    interaction: discord.Interaction,
    member: discord.Member = None
):
    member = member or interaction.user
    roles = [role for role in getattr(member, "roles", []) if role.name != "@everyone"]
    roles = roles[::-1]  # 상단부터 표시
    top_roles = roles[:5] if len(roles) > 5 else roles
    extra_count = len(roles) - 5 if len(roles) > 5 else 0
    roles_display = ", ".join([role.mention for role in top_roles]) if top_roles else "없음"
    if extra_count > 0:
        roles_display += f" +{extra_count}"

    embed = discord.Embed(
        title=f"{member}의 정보",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
    embed.add_field(name="사용자 고유 ID", value=member.id, inline=False)
    embed.add_field(name="별명", value=member.nick if hasattr(member, "nick") and member.nick else "없음", inline=True)
    embed.add_field(name="사용자명", value=member.display_name, inline=True)
    embed.add_field(
        name="계정 생성 시간",
        value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        inline=True
    )
    if hasattr(member, "joined_at") and member.joined_at:
        embed.add_field(
            name="서버 입장 시간",
            value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"),
            inline=True
        )
    embed.add_field(name="역할(최상단 5개)", value=roles_display, inline=True)
    embed.add_field(name="봇 여부", value="봇" if member.bot else "사람", inline=True)
    await interaction.response.send_message(embed=embed)