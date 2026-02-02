import discord
from datetime import datetime
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

def _format_age(dt):
    if not dt:
        return "알 수 없음"
    try:
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
    except Exception:
        pass
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - dt
    days = delta.days
    years = days // 365
    months = (days % 365) // 30
    days_rem = (days % 365) % 30
    parts = []
    if years:
        parts.append(f"{years}년")
    if months:
        parts.append(f"{months}개월")
    if days_rem or not parts:
        parts.append(f"{days_rem}일")
    return f"{dt.strftime('%Y-%m-%d')} ({' '.join(parts)} 전 생성)"


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
        embed.set_footer(text=f"ID: {member.id}")
        embed.add_field(name="계정 생성일", value=_format_age(getattr(member, "created_at", None)), inline=True)
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
        embed.set_footer(text=f"ID: {member.id}")
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
        embed.set_footer(text=f"관리자 ID: {(actor.id if actor else after.id)}")
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
        embed.set_footer(text=f"관리자 ID: {(actor.id if actor else after.id)}")
        await log_channel.send(embed=embed)

# 역할 수정 감지
async def log_role_update(before: discord.Role, after: discord.Role):
    if before.guild is None:
        return
    log_channel = discord.utils.get(before.guild.text_channels, name=LOG_CHANNEL_NAME)
    if not log_channel:
        return

    actor = None
    time = datetime.datetime.now()
    try:
        async for entry in before.guild.audit_logs(limit=6, action=discord.AuditLogAction.role_update):
            if getattr(entry.target, "id", None) == getattr(after, "id", None):
                actor = entry.user
                time = entry.created_at
                break
    except Exception:
        pass

    changes = []

    # 기본 속성
    if getattr(before, "name", None) != getattr(after, "name", None):
        changes.append(("이름", f"`{before.name}` → `{after.name}`"))
    try:
        bcol = before.color.value
        acol = after.color.value
        if bcol != acol:
            changes.append(("색상", f"#{bcol:06x} → #{acol:06x}"))
    except Exception:
        pass
    if getattr(before, "hoist", None) != getattr(after, "hoist", None):
        changes.append(("별도표시", f"{before.hoist} → {after.hoist}"))
    if getattr(before, "mentionable", None) != getattr(after, "mentionable", None):
        changes.append(("언급 가능", f"{before.mentionable} → {after.mentionable}"))
    if getattr(before, "position", None) != getattr(after, "position", None):
        changes.append(("위치", f"{before.position} → {after.position}"))

    # 권한 변경
    def _fmt(val):
        return "🟢 허용" if val is True else "⚪ 거부" if val is False else "➖ 없음"

    perm_names = getattr(discord.Permissions, "VALID_FLAGS", tuple())
    iter_perms = perm_names if perm_names else [attr for attr in dir(before.permissions) if not attr.startswith("_")]

    perm_diffs = []
    for perm in iter_perms:
        try:
            bv = getattr(before.permissions, perm, None)
            av = getattr(after.permissions, perm, None)
        except Exception:
            bv = av = None
        if bv != av:
            perm_diffs.append(f"`{perm}`: {_fmt(bv)} → {_fmt(av)}")

    if perm_diffs:
        # 권한 변경은 각 줄로
        changes.append(("권한", "\n".join(perm_diffs)))

    if not changes:
        return

    mention = getattr(after, "mention", None) or f"`{getattr(after, 'name', None) or getattr(after, 'id', 'unknown')}`"
    embed = discord.Embed(
        title=":gear: 역할 정보 변경",
        description=f"{mention} 역할 정보가 변경되었습니다.",
        color=discord.Color.orange(),
        timestamp=time
    )
    if actor:
        avatar = getattr(actor, "display_avatar", None)
        embed.set_author(name=str(actor), icon_url=avatar.url if avatar else None)

    for name, text in changes:
        embed.add_field(name=name, value=text, inline=False)

    embed.set_footer(text=f"ID: {getattr(after, 'id', 'unknown')}" + (f" | 작업자 ID: {actor.id}" if actor else ""))
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
        embed.add_field(
            name="메시지로 이동",
            value=f"[여기서 보기]({before.jump_url})",
            inline=True
        )
        embed.set_footer(text=f"ID : {after.author.id}")
        await log_channel.send(embed=embed)

# 채널 생성 감지
async def log_channel_create(channel: discord.abc.GuildChannel):
    if channel.guild is None:
        return
    log_channel = discord.utils.get(channel.guild.text_channels, name=LOG_CHANNEL_NAME)
    if not log_channel:
        return

    actor = None
    time = datetime.datetime.now()
    try:
        async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_create):
            if entry.target.id == getattr(channel, "id", None):
                actor = entry.user
                time = entry.created_at
                break
    except Exception:
        pass

    name = getattr(channel, "name", None)
    display_name = f"`{name}`" if name else f"(ID: {getattr(channel, 'id', 'unknown')})"
    type_name = getattr(channel, "type", "unknown")
    type_text = type_name.name if hasattr(type_name, "name") else str(type_name)
    category = getattr(channel, "category", None)
    category_text = category.name if category else "없음"
    mention = getattr(channel, "mention", channel.name)

    embed = discord.Embed(
        title=":heavy_plus_sign: 채널 생성",
        description=f"{mention} 채널이 생성되었습니다.",
        color=discord.Color.green(),
        timestamp=time
    )
    if actor:
        embed.set_author(name=str(actor), icon_url=getattr(actor, "display_avatar", None).url if getattr(actor, "display_avatar", None) else None)
    embed.add_field(name="이름", value=display_name, inline=True)
    embed.add_field(name="종류", value=type_text, inline=True)
    embed.add_field(name="카테고리", value=category_text, inline=True)
    embed.set_footer(text=f"ID: {getattr(channel, 'id', 'unknown')}" + (f" | 작업자 ID: {actor.id}" if actor else ""))
    await log_channel.send(embed=embed)

# 채널 삭제 감지
async def log_channel_delete(channel: discord.abc.GuildChannel):
    if channel.guild is None:
        return
    log_channel = discord.utils.get(channel.guild.text_channels, name=LOG_CHANNEL_NAME)
    if not log_channel:
        return

    actor = None
    time = datetime.datetime.now()
    try:
        async for entry in channel.guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
            if entry.target.id == getattr(channel, "id", None):
                actor = entry.user
                time = entry.created_at
                break
    except Exception:
        pass

    name = getattr(channel, "name", None)
    display_name = f"`{name}`" if name else f"(ID: {getattr(channel, 'id', 'unknown')})"
    type_name = getattr(channel, "type", "unknown")
    type_text = type_name.name if hasattr(type_name, "name") else str(type_name)
    category = getattr(channel, "category", None)
    category_text = category.name if category else "없음"

    embed = discord.Embed(
        title=":wastebasket: 채널 삭제",
        description=f"{display_name} 채널이 삭제되었습니다.",
        color=discord.Color.red(),
        timestamp=time
    )
    if actor:
        embed.set_author(name=str(actor), icon_url=getattr(actor, "display_avatar", None).url if getattr(actor, "display_avatar", None) else None)
    embed.add_field(name="종류", value=type_text, inline=True)
    embed.add_field(name="카테고리", value=category_text, inline=True)
    embed.set_footer(text=f"ID: {getattr(channel, 'id', 'unknown')}" + (f" | 작업자 ID: {actor.id}" if actor else ""))
    await log_channel.send(embed=embed)

# 채널 업데이트
async def log_channel_update(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
    if before.guild is None:
        return
    log_channel = discord.utils.get(before.guild.text_channels, name=LOG_CHANNEL_NAME)
    if not log_channel:
        return

    actor = None
    time = datetime.datetime.now()
    try:
        async for entry in before.guild.audit_logs(limit=6, action=discord.AuditLogAction.channel_update):
            if getattr(entry.target, "id", None) == getattr(after, "id", None):
                actor = entry.user
                time = entry.created_at
                break
    except Exception:
        pass

    changes = []

    # 공통 속성
    if getattr(before, "name", None) != getattr(after, "name", None):
        changes.append(("이름", f"`{before.name}` → `{after.name}`"))
    if getattr(before, "type", None) != getattr(after, "type", None):
        before_type = getattr(before.type, "name", str(before.type))
        after_type = getattr(after.type, "name", str(after.type))
        changes.append(("종류", f"{before_type} → {after_type}"))
    # 카테고리 변경
    bcat = getattr(before, "category", None)
    acat = getattr(after, "category", None)
    if (bcat.name if bcat else None) != (acat.name if acat else None):
        changes.append(("카테고리", f"{bcat.name if bcat else '없음'} → {acat.name if acat else '없음'}"))

    # 텍스트 채널 전용 속성
    if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
        if before.topic != after.topic:
            changes.append(("주제", f"{before.topic or '(없음)'} → {after.topic or '(없음)'}"))
        if before.nsfw != after.nsfw:
            changes.append(("NSFW", f"{before.nsfw} → {after.nsfw}"))
        if before.slowmode_delay != after.slowmode_delay:
            changes.append(("슬로우모드", f"{before.slowmode_delay}초 → {after.slowmode_delay}초"))


    # 음성 채널 전용 속성
    if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
        if before.bitrate != after.bitrate:
            changes.append(("비트레이트", f"{before.bitrate} → {after.bitrate}"))
        if before.user_limit != after.user_limit:
            changes.append(("유저 제한", f"{before.user_limit}명 → {after.user_limit}명"))

    # 권한 변경

    b_overwrites = getattr(before, "overwrites", {}) or {}
    a_overwrites = getattr(after, "overwrites", {}) or {}

    def _target_text(t):
        return getattr(t, "mention", None) or getattr(t, "name", None) or f"(ID:{getattr(t, 'id', str(t))})"

    def _fmt(val):
        return "🟢 허용" if val is True else "❌ 거부" if val is False else "➖ 없음"

    try:
        b_keys = set(b_overwrites.keys())
        a_keys = set(a_overwrites.keys())
    except Exception:
        if getattr(before, "overwrites", None) != getattr(after, "overwrites", None):
            changes.append(("권한", "권한 오버라이드가 변경됨"))
    else:
        added = a_keys - b_keys
        removed = b_keys - a_keys
        changed_entries = []

        perm_names = getattr(discord.Permissions, "VALID_FLAGS", tuple())

        if added:
            # 추가된 대상은 각 줄에 하나씩
            added_lines = "\n".join(
                f"추가: {_target_text(t)}" for t in sorted(added, key=lambda x: getattr(x, "id", str(x))))
            changed_entries.append(added_lines)

        if removed:
            # 제거된 대상은 각 줄에 하나씩
            removed_lines = "\n".join(
                f"제거: {_target_text(t)}" for t in sorted(removed, key=lambda x: getattr(x, "id", str(x))))
            changed_entries.append(removed_lines)

        for target in sorted(b_keys & a_keys, key=lambda x: getattr(x, "id", str(x))):
            b_ow = b_overwrites[target]
            a_ow = a_overwrites[target]
            perm_diffs = []
            if perm_names:
                iter_perms = perm_names
            else:
                iter_perms = [attr for attr in dir(b_ow) if not attr.startswith("_")]

            for perm in iter_perms:
                bv = getattr(b_ow, perm, None)
                av = getattr(a_ow, perm, None)
                if bv != av:
                    perm_diffs.append(f"`{perm}`: {_fmt(bv)} → {_fmt(av)}")

            if perm_diffs:
                # 대상별로 퍼미션 변경을 각 줄에 하나씩 출력
                entry = f"{_target_text(target)}:\n" + "\n".join(perm_diffs)
                changed_entries.append(entry)

        if changed_entries:
            # 대상 블록 간에는 빈 줄로 구분
            changes.append(("권한", "\n\n".join(changed_entries)))

    if not changes:
        return
    mention = getattr(after, "mention",
                      None) or f"`{getattr(before, 'name', None) or getattr(before, 'id', 'unknown')}`"
    embed = discord.Embed(
        title=":wrench: 채널 정보 변경",
        description=f"{mention} 채널 정보가 변경되었습니다.",
        color=discord.Color.orange(),
        timestamp=time
    )
    if actor:
        avatar = getattr(actor, "display_avatar", None)
        embed.set_author(name=str(actor), icon_url=avatar.url if avatar else None)
    for name, text in changes:
        embed.add_field(name=name, value=text, inline=False)

    embed.set_footer(text=f"ID: {getattr(after, 'id', 'unknown')}" + (f" | 작업자 ID: {actor.id}" if actor else ""))
    await log_channel.send(embed=embed)