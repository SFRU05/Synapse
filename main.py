import discord
from discord.ext import commands
import os
from help import help_slash
from infomations.bot_info import info_slash
import datetime
from infomations.server_info import serverinfo_slash
from infomations.user_info import userinfo_slash
from infomations.avatar_info import avatar_slash
from moderation.kick import kick_slash
from moderation.timeout import timeout_slash, pardon_slash
from moderation.ban import ban_slash
from dotenv import load_dotenv
from itertools import cycle
from discord.ext import tasks
from stocks.stock import stock_slash
from stocks.freq_stock import favorites_slash
from logger_db import ensure_db
from discord_logs.log_channel_slash import setlog_slash
from discord_logs.logger import (
    log_message_delete, log_message_edit, log_member_join, log_member_remove,
    log_member_role_update, log_role_update,
    log_channel_create, log_channel_delete, log_channel_update,
)

bot = commands.Bot(command_prefix="-", intents=discord.Intents.all(), help_command=None) # 접두사

def get_status_list():
    return [
        "서버 관리 중",
        "서버 {n}개에서 노는 중",
        "/help로 명령어 확인하기"]

status = cycle(get_status_list())

ensure_db()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN") # TOKEN


    ### 슬래시 커맨드 명령어 모음 ###
bot.tree.add_command(stock_slash) # 주식 보여주기
bot.tree.add_command(favorites_slash) # 자주 보는 주식 보여주기
bot.tree.add_command(help_slash) # Help 명령어
bot.tree.add_command(timeout_slash) # Timeout
bot.tree.add_command(pardon_slash) # Timeout 해제
bot.tree.add_command(kick_slash) # Kick
bot.tree.add_command(ban_slash) # Ban
bot.tree.add_command(avatar_slash) # Avatar 보여주기
bot.tree.add_command(info_slash) # 봇 정보 보여주기
bot.tree.add_command(serverinfo_slash) # 서버 정보 보여주기
bot.tree.add_command(userinfo_slash) # 유저 정보 보여주기
bot.tree.add_command(setlog_slash) # 로그 채널 설정

# 봇이 준비되었을 떄 나오는 상태메시지
@bot.event
async def on_ready():
    print(f"로그인됨: {bot.user.name} ({bot.user.id})")
    await bot.tree.sync() # 슬래시 명령어 동기화
    change_status.start()

@tasks.loop(seconds=10) # n초마다 다음 메시지 출력
async def change_status():
    template = next(status)
    text = template.format(n=len(bot.guilds))
    await bot.change_presence(activity=discord.Game(text))

async def setup_hook():
    await bot.load_extension('random_draw')

bot.setup_hook = setup_hook

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

@bot.command(name="log")
async def log_command(ctx):
    embed = discord.Embed(
        title="로그 설정 방법",
        description="#logs_discord 채팅 채널을 생성하세요.",
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
    # 역할 변경만 감지 (상태, 닉네임 등은 무시)
    if getattr(before, "roles", None) and getattr(after, "roles", None):
        if set(before.roles) != set(after.roles):
            await log_member_role_update(before, after)

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

class BotIntroView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="서포트 서버",
            url="https://discord.gg/kqhzxvNk5y",
            style=discord.ButtonStyle.link,
            emoji="🛠️"
        ))
        self.add_item(discord.ui.Button(
            label="GitHub",
            url="https://github.com/SFRU05/Synapse",  # ← 본인 깃허브 저장소 주소로 변경!
            style=discord.ButtonStyle.link,
            emoji="🌐"
        ))

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    BOT_MENTION = message.guild.me.mention if message.guild else bot.user.mention
    content = message.content.strip()
    if content == BOT_MENTION:
        embed = discord.Embed(
            title="안녕하세요! 👋",
            description=(
                f"다양한 기능들을 수행하는 디스코드 봇, Syanpse입니다.\n\n"
                f"`/help`를 입력하여 명령어를 알아보세요!"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )
        embed.set_footer(text="문의, 피드백: 서포트 서버로 오세요!")
        if bot.user.display_avatar:
            embed.set_thumbnail(url=bot.user.display_avatar.url)

        await message.channel.send(embed=embed, view=BotIntroView())
    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(TOKEN)