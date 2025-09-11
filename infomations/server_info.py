import discord
import datetime

async def send_server_info(ctx):
    guild = ctx.guild
    embed = discord.Embed(
        title=f"{guild.name} 서버 정보",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
    embed.add_field(name="서버 이름", value=guild.name, inline=True)
    embed.add_field(name="서버 ID", value=guild.id, inline=True)
    embed.add_field(name="소유자", value=guild.owner.mention, inline=True)
    embed.add_field(name="멤버 수", value=f"{guild.member_count}명", inline=True)
    embed.add_field(name="생성일", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    await ctx.send(embed=embed)