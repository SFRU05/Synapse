import datetime
import discord
from logger_db import get_log_channel_id


# 메시지 삭제 로그
async def log_message_delete(message: discord.Message):
    if message.guild is None or message.author.bot:
        return
    log_channel_id = get_log_channel_id(message.guild.id)
    if not log_channel_id: return
    log_channel = message.guild.get_channel(log_channel_id)
    if not log_channel: return
    embed = discord.Embed(
        title="🗑️ 메시지 삭제됨",
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

# 메시지 수정 로그
async def log_message_edit(before: discord.Message, after: discord.Message):
    if before.guild is None or before.author.bot:
        return
    if before.content == after.content:
        return
    log_channel_id = get_log_channel_id(before.guild.id)
    if not log_channel_id: return
    log_channel = before.guild.get_channel(log_channel_id)
    if not log_channel: return
    embed = discord.Embed(
        title="✏️ 메시지 수정됨",
        color=discord.Color.teal(),
        timestamp=datetime.datetime.now()
    )
    embed.set_author(name=str(before.author), icon_url=before.author.display_avatar.url)
    embed.add_field(name="수정 전", value=before.content or "(내용 없음)", inline=False)
    embed.add_field(name="수정 후", value=after.content or "(내용 없음)", inline=False)
    embed.add_field(name="채널", value=before.channel.mention, inline=True)
    embed.add_field(
        name="메시지로 이동",
        value=f"[여기서 보기]({before.jump_url})",
        inline=True
    )
    embed.set_footer(text=f"ID: {after.author.id}")
    await log_channel.send(embed=embed)

# 멤버 입장 로그
async def log_member_join(member: discord.Member):
    log_channel_id = get_log_channel_id(member.guild.id)
    if not log_channel_id: return
    log_channel = member.guild.get_channel(log_channel_id)
    if not log_channel: return
    embed = discord.Embed(
        title="🔼 멤버 입장",
        description=f"{member.mention}님이 서버에 들어왔습니다.",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    embed.set_author(name=str(member), icon_url=member.display_avatar.url)
    embed.set_footer(text=f"ID: {member.id}")
    embed.add_field(name="계정 생성일", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    await log_channel.send(embed=embed)

# 멤버 퇴장 로그
async def log_member_remove(member: discord.Member):
    log_channel_id = get_log_channel_id(member.guild.id)
    if not log_channel_id: return
    log_channel = member.guild.get_channel(log_channel_id)
    if not log_channel: return
    embed = discord.Embed(
        title="🔽 멤버 퇴장",
        description=f"{member.mention}님이 서버에서 나갔습니다.",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now()
    )
    embed.set_author(name=str(member), icon_url=member.display_avatar.url)
    embed.set_footer(text=f"ID: {member.id}")
    await log_channel.send(embed=embed)

# 역할 변경 로그 (멤버 역할 변화)
async def log_member_role_update(before: discord.Member, after: discord.Member):
    if before.guild is None:
        return
    log_channel_id = get_log_channel_id(before.guild.id)
    if not log_channel_id: return
    log_channel = before.guild.get_channel(log_channel_id)
    if not log_channel: return

    added_roles = [role for role in after.roles if role not in before.roles]
    removed_roles = [role for role in before.roles if role not in after.roles]
    now = datetime.datetime.now()

    for role in added_roles:
        embed = discord.Embed(
            title="✅ 역할 추가",
            description=f"{after.mention}님에게 역할 {role.mention} 추가됨",
            color=discord.Color.blue(),
            timestamp=now
        )
        embed.set_footer(text=f"ID: {after.id}")
        await log_channel.send(embed=embed)
    for role in removed_roles:
        embed = discord.Embed(
            title="❌ 역할 제거",
            description=f"{after.mention}님에게서 역할 {role.mention} 제거됨",
            color=discord.Color.purple(),
            timestamp=now
        )
        embed.set_footer(text=f"ID: {after.id}")
        await log_channel.send(embed=embed)

# 역할 자체 변경 로그
async def log_role_update(before: discord.Role, after: discord.Role):
    if before.guild is None:
        return
    log_channel_id = get_log_channel_id(before.guild.id)
    if not log_channel_id: return
    log_channel = before.guild.get_channel(log_channel_id)
    if not log_channel: return

    changes = []
    if before.name != after.name:
        changes.append(("이름", f"`{before.name}` → `{after.name}`"))
    if before.color.value != after.color.value:
        changes.append(("색상", f"#{before.color.value:06x} → #{after.color.value:06x}"))
    if before.hoist != after.hoist:
        changes.append(("별도표시", f"{before.hoist} → {after.hoist}"))
    if before.mentionable != after.mentionable:
        changes.append(("언급 가능", f"{before.mentionable} → {after.mentionable}"))
    if before.position != after.position:
        changes.append(("위치", f"{before.position} → {after.position}"))

    if not changes:
        return
    embed = discord.Embed(
        title="⚙️ 역할 정보 변경",
        description=f"{after.mention} 역할 정보가 변경됨",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now()
    )
    for name, value in changes:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=f"ID: {after.id}")
    await log_channel.send(embed=embed)

# 채널 생성 로그
async def log_channel_create(channel: discord.abc.GuildChannel):
    if channel.guild is None: return
    log_channel_id = get_log_channel_id(channel.guild.id)
    if not log_channel_id: return
    log_channel = channel.guild.get_channel(log_channel_id)
    if not log_channel: return
    embed = discord.Embed(
        title="➕ 채널 생성",
        description=f"{channel.mention} 채널 생성",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(text=f"ID: {channel.id}")
    await log_channel.send(embed=embed)

# 채널 삭제 로그
async def log_channel_delete(channel: discord.abc.GuildChannel):
    if channel.guild is None: return
    log_channel_id = get_log_channel_id(channel.guild.id)
    if not log_channel_id: return
    log_channel = channel.guild.get_channel(log_channel_id)
    if not log_channel: return
    embed = discord.Embed(
        title="🗑️ 채널 삭제",
        description=f"`{channel.name}`({channel.id}) 채널 삭제",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(text=f"ID: {channel.id}")
    await log_channel.send(embed=embed)

# 채널 업데이트 로그
async def log_channel_update(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
    if before.guild is None: return
    log_channel_id = get_log_channel_id(before.guild.id)
    if not log_channel_id: return
    log_channel = before.guild.get_channel(log_channel_id)
    if not log_channel: return
    changes = []
    if before.name != after.name:
        changes.append(("이름", f"`{before.name}` → `{after.name}`"))
    if getattr(before, "topic", None) != getattr(after, "topic", None):
        changes.append(("주제", f"{getattr(before, 'topic', None) or '(없음)'} → {getattr(after, 'topic', None) or '(없음)'}"))
    if getattr(before, "position", None) != getattr(after, "position", None):
        changes.append(("위치", f"{getattr(before, 'position', None)} → {getattr(after, 'position', None)}"))
    if not changes:
        return
    embed = discord.Embed(
        title="🔧 채널 정보 변경",
        description=f"{after.mention} 채널 정보가 변경됨",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now()
    )
    for name, value in changes:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=f"ID: {after.id}")
    await log_channel.send(embed=embed)