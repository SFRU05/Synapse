import discord
from discord.ext import commands
import os
from help import send_help
from infomations.bot_info import send_bot_info
from infomations.server_info import send_server_info
from infomations.user_info import send_user_info
from infomations.avatar_info import avatar
from moderation.kick import setup_kick_command
from moderation.timeout import pardon_timeout
from moderation.timeout import setup_timeout_command
from moderation.ban import setup_ban_command
from dotenv import load_dotenv
from itertools import cycle
from discord.ext import tasks
from random_draw import RandomDraw
from logger import log_message_delete, log_member_join, log_member_remove, log_member_role_update, log_message_edit, log_channel_delete, log_channel_create, log_channel_update, log_role_update

bot = commands.Bot(command_prefix="-", intents=discord.Intents.all(), help_command=None) # 접두사

def get_status_list():
    return [
        "서버 관리",
        "음악 듣기",
        f"노는 중"]

status = cycle(get_status_list())

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN") # TOKEN

# 봇이 준비되었을 떄 나오는 상태메시지
@bot.event
async def on_ready():
    print(f"로그인됨: {bot.user.name} ({bot.user.id})")
    await setup_kick_command(bot) # Kick 명령어 실행
    await setup_ban_command(bot) # Ban 명령어 실행
    await setup_timeout_command(bot) # Timeout 명령어 실행
    await pardon_timeout(bot)
    await bot.add_cog(RandomDraw(bot))
    change_status.start()

@tasks.loop(seconds=5) # n초마다 다음 메시지 출력
async def change_status():
    await bot.change_presence(activity=discord.Game(next(status)))

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)  # 봇의 레이턴시(ms 단위)
    embed = discord.Embed(title="🏓 Pong!", description=f"현재 핑: {latency}ms", color=discord.Color.green())
    await ctx.send(embed=embed)

# clear 명령어 - 지정한 개수만큼 메시지 삭제
@bot.command()
async def clear(ctx, amount: int = None):
    if amount is None:
        await ctx.send("삭제할 메시지 개수를 입력하세요. `-clear <개수>`")
        return
    await ctx.channel.purge(limit=amount + 1)
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"요청 **{amount}**개 중 **{len(deleted) - 1}개**의 메시지를 삭제했습니다.")

# help 명령어
@bot.command()
async def help(ctx, category: str = None):
    await send_help(ctx, category)

@bot.command(name="info")
async def info(ctx):
    await send_bot_info(ctx, bot)

@bot.command(name="serverinfo")
async def server_info(ctx):
    await send_server_info(ctx)

@bot.command(name="userinfo")
async def user_info(ctx, member: discord.Member = None):
    await send_user_info(ctx, member)

@bot.command(name="avatar")
async def avatar_info(ctx, member: discord.Member = None):
    await avatar(ctx, member)

@bot.command(name="log")
async def log_command(ctx):
    embed = discord.Embed(
        title="로그 설정 방법",
        description="#logs 채팅 채널을 생성하세요.",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

# 서버 로그 표시
@bot.event
async def on_message_delete(message):
    await log_message_delete(message)

@bot.event
async def on_member_join(member):
    await log_member_join(member)  # 멤버가 서버에 들어왔을 때 로그

@bot.event
async def on_member_remove(member):
    await log_member_remove(member) # 멤버가 서버에서 나갔을 때 로그

@bot.event
async def on_member_update(before, after):
    await log_member_role_update(before, after) # 멤버의 역할이 변경되었을 때 로그

@bot.event
async def on_message_edit(before, after):
    await log_message_edit(before, after) # 메시지가 수정되었을 때 로그

@bot.event
async def on_message_edit(before, after):
    await log_message_edit(before, after)

@bot.event
async def on_guild_channel_create(channel):
    await log_channel_create(channel)

@bot.event
async def on_guild_channel_delete(channel):
    await log_channel_delete(channel)

@bot.event
async def on_guild_channel_update(before, after):
    await log_channel_update(before, after)

@bot.event
async def on_guild_role_update(before: discord.Role, after: discord.Role):
    await log_role_update(before, after)

if __name__ == "__main__":
    bot.run(TOKEN)