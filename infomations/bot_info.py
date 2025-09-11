import discord
import time
import sys
import datetime

start_time = time.time()

async def send_bot_info(ctx, bot):
    current_time = time.time()
    uptime_seconds = int(current_time - start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}시간 {minutes}분 {seconds}초"
    python_version = sys.version.split()[0]
    discord_version = discord.__version__

    embed = discord.Embed(
        title="봇 정보",
        color=discord.Color.purple(),
        timestamp=datetime.datetime.now(datetime.UTC)
    )
    embed.add_field(name="이름", value=bot.user.name, inline=True)
    embed.add_field(name="ID", value=bot.user.id, inline=True)
    embed.add_field(name="업타임", value=uptime_str, inline=False)
    embed.add_field(name="사용 언어", value='`Python`', inline=True)
    embed.add_field(name="버전", value=python_version, inline=True)
    embed.add_field(name="API 버전", value=discord_version, inline=True)
    embed.add_field(name="서버 수", value=f"{len(bot.guilds)}개", inline=True)
    embed.set_footer(text="Synapse Bot")
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    await ctx.send(embed=embed)