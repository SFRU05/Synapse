import discord
from datetime import datetime, timezone
import datetime

LOG_CHANNEL_NAME = "logs"

async def log_message_delete(message: discord.Message):
    if message.guild is None or message.author.bot:
        return
    log_channel = discord.utils.get(message.guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        embed = discord.Embed(
            title=":thought_balloon: 메시지 삭제됨",
            description=message.content or "(내용 없음)",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        if message.attachments:
            first = message.attachments[0]
            if first.content_type and first.content_type.startswith("image"):
                embed.set_image(url=first.url)
            urls = "\n".join(a.url for a in message.attachments)
            embed.add_field(name="첨부파일", value=urls, inline=False)
        embed.add_field(name="채널", value=message.channel.mention, inline=True)
        await log_channel.send(embed=embed)

async def log_member_join(member: discord.Member):
    log_channel = discord.utils.get(member.guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        embed = discord.Embed(
            title=":chart_with_upwards_trend: 멤버 입장",
            description=f"{member.mention}님이 서버에 들어왔습니다.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        await log_channel.send(embed=embed)

async def log_member_remove(member: discord.Member):
    log_channel = discord.utils.get(member.guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        embed = discord.Embed(
            title=":chart_with_downwards_trend: 멤버 퇴장",
            description=f"{member.mention}님이 서버에서 나갔습니다.",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)

        await log_channel.send(embed=embed)
# 역할 로그
async def log_member_role_update(before: discord.Member, after: discord.Member):
    if before.guild is None:
        return
    log_channel = discord.utils.get(before.guild.text_channels, name=LOG_CHANNEL_NAME)
    if not log_channel:
        return

    # 역할 변화 감지
    added_roles = [role for role in after.roles if role not in before.roles]
    removed_roles = [role for role in before.roles if role not in after.roles]

    # 역할 추가 로그
    for role in added_roles:
        # 감사 로그에서 최근 역할 추가 액션 찾기
        async for entry in before.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
            if entry.target.id == after.id and role in entry.changes.after:
                actor = entry.user
                time = entry.created_at
                break
        else:
            actor = None
            time = datetime.datetime.now()
        embed = discord.Embed(
            title=":white_check_mark: 역할 추가",
            description=f"{after.mention}님에게 역할 {role.mention}이(가) 추가됨",
            color=discord.Color.blue(),
            timestamp=time
        )
        if actor:
            embed.set_author(name=f"수행자: {actor}", icon_url=actor.display_avatar.url)
        await log_channel.send(embed=embed)

    # 역할 제거 로그
    for role in removed_roles:
        async for entry in before.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
            if entry.target.id == after.id and role in entry.changes.before:
                actor = entry.user
                time = entry.created_at
                break
        else:
            actor = None
            time = datetime.datetime.now()
        embed = discord.Embed(
            title=":x: 역할 제거",
            description=f"{after.mention}님에게서 역할 {role.mention}이(가) 제거됨",
            color=discord.Color.purple(),
            timestamp=time
        )
        if actor:
            embed.set_author(name=f"수행자: {actor}", icon_url=actor.display_avatar.url)
        await log_channel.send(embed=embed)

async def log_message_edit(before: discord.Message, after: discord.Message):
    if before.guild is None or before.author.bot:
        return
    if before.content == after.content:
        return  # 내용이 바뀌지 않았으면 무시
    log_channel = discord.utils.get(before.guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        embed = discord.Embed(
            title=":pencil: 메시지 수정됨",
            color=discord.Color.teal(),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=str(before.author), icon_url=before.author.display_avatar.url)
        embed.add_field(name="수정 전", value=before.content or "(내용 없음)", inline=False)
        embed.add_field(name="수정 후", value=after.content or "(내용 없음)", inline=False)
        embed.add_field(name="채널", value=before.channel.mention, inline=True)
        await log_channel.send(embed=embed)