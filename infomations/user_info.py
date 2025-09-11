import discord

async def send_user_info(ctx, member: discord.Member = None):
    member = member or ctx.author
    roles = [role for role in member.roles if role.name != "@everyone"]
    roles = roles[::-1]  # 역할을 최상단부터 표시
    top_roles = roles[:5] if len(roles) > 5 else roles
    extra_count = len(roles) - 5 if len(roles) > 5 else 0
    roles_display = ", ".join([role.mention for role in top_roles])
    if extra_count > 0:
        roles_display += f" +{extra_count}"
    embed = discord.Embed(
        title=f"{member}의 정보",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else discord.Embed.Empty)
    embed.add_field(name="사용자 고유 ID", value=member.id, inline=False)
    embed.add_field(name="별명", value=member.nick if member.nick else "없음", inline=True)
    embed.add_field(name="계정 생성 시간", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name="사용자명", value=member.display_name, inline=True)
    embed.add_field(name="역할(최상단 5개)", value=roles_display if roles_display else "없음", inline=True)
    embed.add_field(name="서버 입장 시간", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name="봇 여부", value="봇" if member.bot else "사람", inline=True)
    await ctx.send(embed=embed)