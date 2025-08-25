import discord
from discord.ext import commands
import music
import os
from dotenv import load_dotenv
from logger import log_message_delete, log_member_join, log_member_remove, log_member_role_update, log_message_edit

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN") # TOKEN

bot = commands.Bot(command_prefix="-", intents=discord.Intents.all(), help_command=None) # 접두사

# 봇이 준비되었을 떄 나오는 상태메시지
@bot.event
async def on_ready():
    print(f"로그인됨: {bot.user.name} ({bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="서버 관리"))

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)  # 봇의 레이턴시(ms 단위)
    embed = discord.Embed(title="🏓 Pong!", description=f"현재 핑: {latency}ms", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command()
async def test(ctx):
    await ctx.send('hello')

# clear 명령어 - 지정한 개수만큼 메시지 삭제
@bot.command()
async def clear(ctx, amount: int = None):
    if amount is None:
        await ctx.send("삭제할 메시지 개수를 입력하세요. `-clear <개수>`")
        return
    await ctx.channel.purge(limit=amount + 1)
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"요청 **{amount}**개 중 **{len(deleted)}개**의 메시지를 삭제했습니다.")

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="도움말", description="사용 가능한 명령어 목록입니다.", color=discord.Color.blue())
    embed.add_field(name="-join", value="봇을 음성 채널에 참여시킵니다.", inline=False)
    embed.add_field(name="-leave", value="봇을 음성 채널에서 나가게 합니다.", inline=False)
    embed.add_field(name="-play <URL>", value="지정한 URL의 음악을 재생합니다.", inline=False)
    embed.add_field(name="-skip", value="현재 재생 중인 곡을 스킵합니다.", inline=False)
    embed.add_field(name="-queue", value="현재 대기열을 확인합니다.", inline=False)
    embed.add_field(name="-stop", value="음악을 정지하고 대기열을 비웁니다.", inline=False)
    embed.add_field(name="-clear <개수>", value="지정한 개수만큼 메시지를 삭제합니다.", inline=False)
    embed.add_field(name="-ping", value="봇의 응답 속도를 확인합니다.", inline=False)
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

if __name__ == "__main__":
    music.setup(bot)
    bot.run(TOKEN)