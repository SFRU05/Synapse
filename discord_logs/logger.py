import asyncio
import datetime
import logging
from collections.abc import Iterable

import discord

from .log_settings_db import (
    get_log_channel_id,
    get_log_settings,
)


logger = logging.getLogger(__name__)


# ============================================================
# 설정
# ============================================================

CHANNEL_POSITION_DEBOUNCE_SECONDS = 1.2

AUDIT_LOG_LIMIT = 50
AUDIT_LOG_MAX_AGE_SECONDS = 30
AUDIT_LOG_RETRY_COUNT = 5
AUDIT_LOG_RETRY_DELAY_SECONDS = 0.6


# ============================================================
# 채널 위치 변경 임시 저장소
# ============================================================

# guild_id -> channel_id -> (이전 위치, 최종 위치)
_pending_channel_position_changes: dict[
    int,
    dict[int, tuple[int, int]]
] = {}

# guild_id -> asyncio.Task
_channel_position_flush_tasks: dict[int, asyncio.Task] = {}


# ============================================================
# 공통 함수
# ============================================================

def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def get_setting(
    settings: dict,
    key: str,
    default: bool = True
) -> bool:
    return bool(settings.get(key, default))


def get_log_channel(
    guild: discord.Guild
) -> discord.abc.Messageable | None:
    try:
        channel_id = get_log_channel_id(guild.id)

        if not channel_id:
            return None

        return guild.get_channel(channel_id)

    except Exception:
        logger.exception(
            "로그 채널 조회 중 오류가 발생했습니다. guild_id=%s",
            guild.id
        )
        return None


async def send_log(
    guild: discord.Guild,
    embed: discord.Embed
) -> bool:
    """
    로그 전송 실패가 봇 전체에 영향을 주지 않도록 처리합니다.
    """
    log_channel = get_log_channel(guild)

    if log_channel is None:
        return False

    try:
        await log_channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=True,
                everyone=False
            )
        )
        return True

    except discord.Forbidden:
        logger.warning(
            "로그 채널에 메시지를 보낼 권한이 없습니다. guild_id=%s",
            guild.id
        )
        return False

    except discord.HTTPException:
        logger.exception(
            "로그 전송 중 Discord API 오류가 발생했습니다. guild_id=%s",
            guild.id
        )
        return False

    except Exception:
        logger.exception(
            "로그 전송 중 알 수 없는 오류가 발생했습니다. guild_id=%s",
            guild.id
        )
        return False


def set_actor(
    embed: discord.Embed,
    actor: discord.User | discord.Member | None,
    *,
    fallback_name: str = "실행자 확인 불가"
):
    """
    작업자를 Embed author에 표시합니다.

    Author:
        작업자 이름 + 프로필 사진

    Footer:
        작업자 ID
    """
    if actor is None:
        embed.set_author(name=fallback_name)
        embed.set_footer(text="작업자 ID: 확인 불가")
        return

    try:
        avatar_url = actor.display_avatar.url
    except Exception:
        avatar_url = None

    if avatar_url:
        embed.set_author(
            name=str(actor),
            icon_url=avatar_url
        )
    else:
        embed.set_author(name=str(actor))

    actor_id = getattr(actor, "id", None)

    embed.set_footer(
        text=(
            f"작업자 ID: {actor_id}"
            if actor_id is not None
            else "작업자 ID: 확인 불가"
        )
    )


def set_member_author(
    embed: discord.Embed,
    member: discord.Member | discord.User
):
    """
    입장·자발적 퇴장 로그에 대상 멤버를 표시합니다.
    """
    try:
        avatar_url = member.display_avatar.url
    except Exception:
        avatar_url = None

    if avatar_url:
        embed.set_author(
            name=str(member),
            icon_url=avatar_url
        )
    else:
        embed.set_author(name=str(member))

    embed.set_footer(
        text=f"멤버 ID: {member.id}"
    )


def format_role_list(
    roles: list[discord.Role]
) -> str:
    """
    역할이 하나면 불릿 없이 표시하고,
    여러 개면 불릿을 표시합니다.
    """
    if not roles:
        return "없음"

    if len(roles) == 1:
        return roles[0].mention

    return "\n".join(
        f"• {role.mention}"
        for role in roles
    )


def format_permission_name(
    permission_name: str
) -> str:
    return permission_name.replace("_", " ").title()


def format_permission_list(
    permissions: list[str]
) -> str:
    """
    권한이 하나면 불릿 없이 표시하고,
    여러 개면 불릿을 표시합니다.
    """
    if not permissions:
        return "없음"

    if len(permissions) == 1:
        return permissions[0]

    return "\n".join(
        f"• {permission}"
        for permission in permissions
    )


def format_audit_reason(
    entry: discord.AuditLogEntry | None
) -> str:
    if entry is None:
        return "감사 로그에서 확인할 수 없음"

    reason = getattr(entry, "reason", None)

    if reason is None or not str(reason).strip():
        return "사유가 입력되지 않았어요."

    return str(reason)


def format_target_user(
    user: discord.User | discord.Member
) -> str:
    display_name = getattr(
        user,
        "display_name",
        str(user)
    )

    return (
        f"{display_name}\n"
        f"ID: `{user.id}`"
    )


def get_audit_target_id(
    entry: discord.AuditLogEntry
) -> int | None:
    target = getattr(entry, "target", None)
    return getattr(target, "id", None)


def get_audit_entry_age(
    entry: discord.AuditLogEntry,
    now: datetime.datetime
) -> float | None:
    created_at = getattr(entry, "created_at", None)

    if created_at is None:
        return None

    if created_at.tzinfo is None:
        created_at = created_at.replace(
            tzinfo=datetime.timezone.utc
        )

    return (now - created_at).total_seconds()


# ============================================================
# 감사 로그 조회
# ============================================================

async def find_audit_log_entry(
    guild: discord.Guild,
    *,
    actions: (
        discord.AuditLogAction
        | Iterable[discord.AuditLogAction]
    ),
    target_ids: set[int] | None = None,
    max_age_seconds: int = AUDIT_LOG_MAX_AGE_SECONDS,
    retry_count: int = AUDIT_LOG_RETRY_COUNT,
    retry_delay: float = AUDIT_LOG_RETRY_DELAY_SECONDS,
) -> tuple[
    discord.AuditLogEntry | None,
    discord.User | discord.Member | None
]:
    """
    최근 감사 로그 항목과 작업자를 조회합니다.

    찾지 못하면 (None, None)을 반환합니다.
    """
    if isinstance(actions, discord.AuditLogAction):
        action_list = [actions]
    else:
        action_list = list(actions)

    target_ids = target_ids or set()

    for attempt in range(retry_count + 1):
        now = utc_now()

        try:
            for action in action_list:
                async for entry in guild.audit_logs(
                    limit=AUDIT_LOG_LIMIT,
                    action=action
                ):
                    age = get_audit_entry_age(entry, now)

                    if age is None or age < 0:
                        continue

                    if age > max_age_seconds:
                        break

                    target_id = get_audit_target_id(entry)

                    if target_ids and target_id not in target_ids:
                        continue

                    actor = getattr(entry, "user", None)

                    if actor is not None:
                        return entry, actor

            if attempt < retry_count:
                await asyncio.sleep(retry_delay)

        except discord.Forbidden:
            logger.warning(
                "감사 로그 보기 권한이 없습니다. guild_id=%s",
                guild.id
            )
            return None, None

        except discord.HTTPException:
            logger.warning(
                "감사 로그 조회에 실패했습니다. "
                "attempt=%s/%s guild_id=%s",
                attempt + 1,
                retry_count + 1,
                guild.id
            )

            if attempt < retry_count:
                await asyncio.sleep(retry_delay)

        except Exception:
            logger.exception(
                "감사 로그 처리 중 오류가 발생했습니다. guild_id=%s",
                guild.id
            )
            return None, None

    return None, None


# ============================================================
# 권한 비교
# ============================================================

def get_permission_changes(
    before: discord.Permissions,
    after: discord.Permissions
) -> tuple[list[str], list[str]]:
    before_values = dict(before)
    after_values = dict(after)

    added_permissions = []
    removed_permissions = []

    all_names = (
        set(before_values)
        | set(after_values)
    )

    for permission_name in sorted(all_names):
        before_value = before_values.get(
            permission_name,
            False
        )

        after_value = after_values.get(
            permission_name,
            False
        )

        if before_value == after_value:
            continue

        display_name = format_permission_name(
            permission_name
        )

        if after_value:
            added_permissions.append(display_name)
        else:
            removed_permissions.append(display_name)

    return added_permissions, removed_permissions


def get_overwrite_snapshot(
    channel: discord.abc.GuildChannel
) -> dict[
    int,
    tuple[object, discord.PermissionOverwrite]
]:
    snapshot = {}

    try:
        overwrites = channel.overwrites
    except AttributeError:
        return snapshot

    for target, overwrite in overwrites.items():
        target_id = getattr(target, "id", None)

        if target_id is not None:
            snapshot[target_id] = (
                target,
                overwrite
            )

    return snapshot


def get_overwrite_permission_changes(
    before: discord.PermissionOverwrite,
    after: discord.PermissionOverwrite
) -> tuple[list[str], list[str]]:
    before_values = dict(before)
    after_values = dict(after)

    added_permissions = []
    removed_permissions = []

    all_names = (
        set(before_values)
        | set(after_values)
    )

    for permission_name in sorted(all_names):
        before_value = before_values.get(
            permission_name,
            None
        )

        after_value = after_values.get(
            permission_name,
            None
        )

        if before_value == after_value:
            continue

        display_name = format_permission_name(
            permission_name
        )

        if after_value is True:
            added_permissions.append(
                f"{display_name}: 허용"
            )

        elif after_value is False:
            removed_permissions.append(
                f"{display_name}: 거부"
            )

        elif after_value is None:
            if before_value is True:
                removed_permissions.append(
                    f"{display_name}: 없음"
                )
            elif before_value is False:
                added_permissions.append(
                    f"{display_name}: 없음"
                )

    return added_permissions, removed_permissions


def format_permission_target(
    target: object | None,
    target_id: int,
    guild: discord.Guild | None = None
) -> str:
    """
    역할은 역할 멘션,
    멤버는 사용자 멘션으로 표시합니다.
    """
    if guild is not None:
        role = guild.get_role(target_id)

        if role is not None:
            return role.mention

        member = guild.get_member(target_id)

        if member is not None:
            return member.mention

    if isinstance(target, discord.Role):
        return target.mention

    if isinstance(target, discord.Member):
        return target.mention

    if isinstance(target, discord.User):
        return target.mention

    target_name = getattr(target, "name", None)

    if target_name:
        return str(target_name)

    return f"대상 ID: `{target_id}`"


def format_new_overwrite(
    overwrite: discord.PermissionOverwrite
) -> str:
    allowed = []
    denied = []

    for permission_name, value in dict(overwrite).items():
        display_name = format_permission_name(
            permission_name
        )

        if value is True:
            allowed.append(
                f"{display_name}: 허용"
            )

        elif value is False:
            denied.append(
                f"{display_name}: 거부"
            )

    lines = []

    if allowed:
        lines.append(
            "✅ 허용\n"
            + format_permission_list(allowed)
        )

    if denied:
        lines.append(
            "❌ 거부\n"
            + format_permission_list(denied)
        )

    return (
        "\n\n".join(lines)
        or "권한 덮어쓰기가 생성되었어요."
    )


def format_existing_overwrite_change(
    before: discord.PermissionOverwrite,
    after: discord.PermissionOverwrite
) -> str:
    added, removed = get_overwrite_permission_changes(
        before,
        after
    )

    lines = []

    if added:
        lines.append(
            "✅ 변경된 권한\n"
            + format_permission_list(added)
        )

    if removed:
        lines.append(
            "❌ 변경된 권한\n"
            + format_permission_list(removed)
        )

    return (
        "\n\n".join(lines)
        or "권한 변경 내용을 확인할 수 없습니다."
    )


# ============================================================
# 메시지 삭제
# ============================================================

# 메시지 삭제 로그
async def log_message_delete(
    message: discord.Message
):
    if message.guild is None or message.author.bot:
        return

    settings = get_log_settings(message.guild.id)

    if not settings["message_delete"]:
        return

    log_channel_id = get_log_channel_id(
        message.guild.id
    )

    if not log_channel_id:
        return

    log_channel = message.guild.get_channel(
        log_channel_id
    )

    if not log_channel:
        return

    embed = discord.Embed(
        title="🗑️ 메시지가 삭제되었어요",
        description=message.content or "(내용 없음)",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now()
    )

    # 기존 방식처럼 메시지 작성자를 표시합니다.
    embed.set_author(
        name=str(message.author),
        icon_url=message.author.display_avatar.url
    )

    if message.attachments:
        first_attachment = message.attachments[0]

        if (
            first_attachment.content_type
            and first_attachment.content_type.startswith("image")
        ):
            embed.set_image(
                url=first_attachment.url
            )

        attachment_urls = "\n".join(
            attachment.url
            for attachment in message.attachments
        )

        embed.add_field(
            name="첨부파일",
            value=attachment_urls,
            inline=False
        )

    embed.add_field(
        name="채널",
        value=message.channel.mention,
        inline=True
    )

    embed.set_footer(
        text=f"작성자 ID: {message.author.id}"
    )

    await log_channel.send(
        embed=embed
    )


# ============================================================
# 메시지 수정
# ============================================================

async def log_message_edit(
    before: discord.Message,
    after: discord.Message
):
    if before.guild is None:
        return

    if before.author.bot:
        return

    if before.content == after.content:
        return

    try:
        settings = get_log_settings(before.guild.id)

        if not get_setting(settings, "message_edit"):
            return

        embed = discord.Embed(
            title="✏️ 메시지가 수정되었어요",
            color=discord.Color.teal(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            before.author,
            fallback_name="메시지 작성자"
        )

        embed.add_field(
            name="수정 전",
            value=before.content or "(내용 없음)",
            inline=False
        )

        embed.add_field(
            name="수정 후",
            value=after.content or "(내용 없음)",
            inline=False
        )

        embed.add_field(
            name="채널",
            value=before.channel.mention,
            inline=True
        )

        embed.add_field(
            name="메시지로 이동",
            value=f"[여기서 보기]({before.jump_url})",
            inline=True
        )

        await send_log(before.guild, embed)

    except Exception:
        logger.exception(
            "메시지 수정 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 멤버 입장
# ============================================================

async def log_member_join(
    member: discord.Member
):
    try:
        settings = get_log_settings(member.guild.id)

        if not get_setting(settings, "member_join"):
            return

        embed = discord.Embed(
            title="➡️ 멤버 입장",
            description=(
                f"{member.mention}님이 "
                "서버에 들어오셨어요."
            ),
            color=discord.Color.green(),
            timestamp=utc_now()
        )

        set_member_author(embed, member)

        embed.add_field(
            name="계정 생성일",
            value=member.created_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            inline=True
        )

        embed.add_field(
            name="멤버 ID",
            value=f"`{member.id}`",
            inline=True
        )

        await send_log(member.guild, embed)

    except Exception:
        logger.exception(
            "멤버 입장 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 멤버 퇴장·추방
# ============================================================

async def log_member_remove(
    member: discord.Member
):
    """
    discord.py에는 on_member_kick 이벤트가 없으므로
    on_member_remove에서 감사 로그로 추방 여부를 확인합니다.
    """
    if member.guild is None:
        return

    try:
        settings = get_log_settings(member.guild.id)

        remove_enabled = get_setting(
            settings,
            "member_remove"
        )

        kick_enabled = get_setting(
            settings,
            "member_kick"
        )

        ban_enabled = get_setting(
            settings,
            "member_ban"
        )

        if not any(
            (
                remove_enabled,
                kick_enabled,
                ban_enabled
            )
        ):
            return

        # 차단 시 on_member_ban에서 이미 기록하므로
        # 일반 퇴장 로그를 중복 전송하지 않습니다.
        if ban_enabled:
            ban_entry, _ = await find_audit_log_entry(
                member.guild,
                actions=discord.AuditLogAction.ban,
                target_ids={member.id},
                max_age_seconds=20,
                retry_count=3,
                retry_delay=0.4
            )

            if ban_entry is not None:
                return

        # 추방 여부 확인
        if kick_enabled:
            kick_entry, kick_actor = (
                await find_audit_log_entry(
                    member.guild,
                    actions=discord.AuditLogAction.kick,
                    target_ids={member.id},
                    max_age_seconds=20,
                    retry_count=5,
                    retry_delay=0.5
                )
            )

            if kick_entry is not None:
                embed = discord.Embed(
                    title="👢 멤버가 추방되었어요",
                    description=(
                        f"{member.mention}님이 "
                        "서버에서 추방되었어요."
                    ),
                    color=discord.Color.orange(),
                    timestamp=utc_now()
                )

                set_actor(
                    embed,
                    kick_actor,
                    fallback_name="추방 실행자 확인 불가"
                )

                embed.add_field(
                    name="대상 멤버",
                    value=format_target_user(member),
                    inline=False
                )

                embed.add_field(
                    name="사유",
                    value=format_audit_reason(kick_entry),
                    inline=False
                )

                await send_log(member.guild, embed)
                return

        # 자발적 퇴장
        if not remove_enabled:
            return

        embed = discord.Embed(
            title="⬅️ 멤버 퇴장",
            description=(
                f"{member.mention}님이 "
                "서버에서 나갔어요."
            ),
            color=discord.Color.orange(),
            timestamp=utc_now()
        )

        set_member_author(embed, member)

        embed.add_field(
            name="멤버",
            value=format_target_user(member),
            inline=False
        )

        await send_log(member.guild, embed)

    except Exception:
        logger.exception(
            "멤버 퇴장 또는 추방 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 멤버 차단
# ============================================================

async def log_member_ban(
    guild: discord.Guild,
    user: discord.User
):
    try:
        settings = get_log_settings(guild.id)

        if not get_setting(settings, "member_ban"):
            return

        entry, actor = await find_audit_log_entry(
            guild,
            actions=discord.AuditLogAction.ban,
            target_ids={user.id},
            max_age_seconds=30,
            retry_count=5,
            retry_delay=0.6
        )

        embed = discord.Embed(
            title="🔨 멤버가 차단되었어요",
            description=(
                f"{user.mention}님이 "
                "서버에서 차단되었어요."
            ),
            color=discord.Color.red(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            actor,
            fallback_name="차단 실행자 확인 불가"
        )

        embed.add_field(
            name="대상 멤버",
            value=format_target_user(user),
            inline=False
        )

        embed.add_field(
            name="사유",
            value=format_audit_reason(entry),
            inline=False
        )

        await send_log(guild, embed)

    except Exception:
        logger.exception(
            "멤버 차단 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 멤버 차단 해제
# ============================================================

async def log_member_unban(
    guild: discord.Guild,
    user: discord.User
):
    try:
        settings = get_log_settings(guild.id)

        if not get_setting(settings, "member_unban"):
            return

        entry, actor = await find_audit_log_entry(
            guild,
            actions=discord.AuditLogAction.unban,
            target_ids={user.id},
            max_age_seconds=30,
            retry_count=5,
            retry_delay=0.6
        )

        embed = discord.Embed(
            title="🔓 차단이 해제되었어요",
            description=(
                f"{user.mention}님의 "
                "차단이 해제되었어요."
            ),
            color=discord.Color.green(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            actor,
            fallback_name="차단 해제 실행자 확인 불가"
        )

        embed.add_field(
            name="대상 멤버",
            value=format_target_user(user),
            inline=False
        )

        embed.add_field(
            name="사유",
            value=format_audit_reason(entry),
            inline=False
        )

        await send_log(guild, embed)

    except Exception:
        logger.exception(
            "멤버 차단 해제 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 멤버 역할 변경
# ============================================================

async def log_member_role_update(
    before: discord.Member,
    after: discord.Member
):
    if before.guild is None:
        return

    try:
        settings = get_log_settings(before.guild.id)

        if not get_setting(
            settings,
            "member_role_update"
        ):
            return

        added_roles = [
            role
            for role in after.roles
            if role not in before.roles
        ]

        removed_roles = [
            role
            for role in before.roles
            if role not in after.roles
        ]

        if not added_roles and not removed_roles:
            return

        _, actor = await find_audit_log_entry(
            after.guild,
            actions=discord.AuditLogAction.member_role_update,
            target_ids={after.id},
            max_age_seconds=20,
            retry_count=5,
            retry_delay=0.5
        )

        embed = discord.Embed(
            title="👤 멤버 역할 변경",
            description=(
                f"{after.mention}님의 역할이 변경되었어요."
            ),
            color=discord.Color.blurple(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            actor,
            fallback_name="실행자 확인 불가"
        )

        if added_roles:
            embed.add_field(
                name="✅ 추가된 역할",
                value=format_role_list(added_roles),
                inline=False
            )

        if removed_roles:
            embed.add_field(
                name="❌ 제거된 역할",
                value=format_role_list(removed_roles),
                inline=False
            )

        embed.add_field(
            name="대상 멤버",
            value=(
                f"{after.mention}\n"
                f"ID: `{after.id}`"
            ),
            inline=False
        )

        await send_log(after.guild, embed)

    except Exception:
        logger.exception(
            "멤버 역할 변경 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 역할 생성
# ============================================================

async def log_role_create(
    role: discord.Role
):
    if role.guild is None:
        return

    try:
        settings = get_log_settings(role.guild.id)

        if not get_setting(settings, "role_create"):
            return

        _, actor = await find_audit_log_entry(
            role.guild,
            actions=discord.AuditLogAction.role_create,
            target_ids={role.id}
        )

        embed = discord.Embed(
            title="➕ 역할 생성됨",
            description=(
                f"{role.mention} 역할이 생성되었어요."
            ),
            color=discord.Color.green(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            actor,
            fallback_name="실행자 확인 불가"
        )

        embed.add_field(
            name="역할명",
            value=role.name,
            inline=True
        )

        embed.add_field(
            name="색상",
            value=f"#{role.color.value:06x}",
            inline=True
        )

        embed.add_field(
            name="역할 ID",
            value=f"`{role.id}`",
            inline=False
        )

        await send_log(role.guild, embed)

    except Exception:
        logger.exception(
            "역할 생성 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 역할 삭제
# ============================================================

async def log_role_delete(
    role: discord.Role
):
    if role.guild is None:
        return

    try:
        settings = get_log_settings(role.guild.id)

        if not get_setting(settings, "role_delete"):
            return

        _, actor = await find_audit_log_entry(
            role.guild,
            actions=discord.AuditLogAction.role_delete,
            target_ids={role.id}
        )

        embed = discord.Embed(
            title="🗑️ 역할 삭제됨",
            description=(
                f"`{role.name}` 역할이 삭제되었어요."
            ),
            color=discord.Color.red(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            actor,
            fallback_name="실행자 확인 불가"
        )

        embed.add_field(
            name="역할 ID",
            value=f"`{role.id}`",
            inline=False
        )

        await send_log(role.guild, embed)

    except Exception:
        logger.exception(
            "역할 삭제 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 역할 정보·권한 변경
# ============================================================

async def log_role_update(
    before: discord.Role,
    after: discord.Role
):
    if before.guild is None:
        return

    try:
        settings = get_log_settings(before.guild.id)

        info_enabled = get_setting(
            settings,
            "role_update"
        )

        permission_enabled = get_setting(
            settings,
            "role_permissions_update"
        )

        info_changes = []

        if before.name != after.name:
            info_changes.append(
                (
                    "이름",
                    f"`{before.name}` → `{after.name}`"
                )
            )

        if before.color.value != after.color.value:
            info_changes.append(
                (
                    "색상",
                    f"#{before.color.value:06x} → "
                    f"#{after.color.value:06x}"
                )
            )

        if before.hoist != after.hoist:
            info_changes.append(
                (
                    "별도 표시",
                    f"{before.hoist} → {after.hoist}"
                )
            )

        if before.mentionable != after.mentionable:
            info_changes.append(
                (
                    "언급 가능",
                    f"{before.mentionable} → "
                    f"{after.mentionable}"
                )
            )

        if before.position != after.position:
            info_changes.append(
                (
                    "위치",
                    f"{before.position} → {after.position}"
                )
            )

        added_permissions, removed_permissions = (
            get_permission_changes(
                before.permissions,
                after.permissions
            )
        )

        if info_enabled and info_changes:
            _, actor = await find_audit_log_entry(
                before.guild,
                actions=discord.AuditLogAction.role_update,
                target_ids={after.id}
            )

            embed = discord.Embed(
                title="⚙️ 역할 정보 변경됨",
                description=(
                    f"{after.mention} 역할의 정보가 변경되었어요."
                ),
                color=discord.Color.orange(),
                timestamp=utc_now()
            )

            set_actor(
                embed,
                actor,
                fallback_name="실행자 확인 불가"
            )

            for name, value in info_changes:
                embed.add_field(
                    name=name,
                    value=value,
                    inline=False
                )

            await send_log(before.guild, embed)

        if (
            permission_enabled
            and (
                added_permissions
                or removed_permissions
            )
        ):
            _, actor = await find_audit_log_entry(
                before.guild,
                actions=discord.AuditLogAction.role_update,
                target_ids={after.id}
            )

            embed = discord.Embed(
                title="🔐 역할 권한 변경됨",
                description=(
                    f"{after.mention} 역할의 권한이 변경되었어요."
                ),
                color=discord.Color.gold(),
                timestamp=utc_now()
            )

            set_actor(
                embed,
                actor,
                fallback_name="실행자 확인 불가"
            )

            if added_permissions:
                embed.add_field(
                    name="✅ 추가된 권한",
                    value=format_permission_list(
                        added_permissions
                    ),
                    inline=False
                )

            if removed_permissions:
                embed.add_field(
                    name="❌ 제거된 권한",
                    value=format_permission_list(
                        removed_permissions
                    ),
                    inline=False
                )

            embed.add_field(
                name="역할 ID",
                value=f"`{after.id}`",
                inline=False
            )

            await send_log(before.guild, embed)

    except Exception:
        logger.exception(
            "역할 변경 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 채널 생성
# ============================================================

async def log_channel_create(
    channel: discord.abc.GuildChannel
):
    if channel.guild is None:
        return

    try:
        settings = get_log_settings(channel.guild.id)

        if not get_setting(settings, "channel_create"):
            return

        _, actor = await find_audit_log_entry(
            channel.guild,
            actions=discord.AuditLogAction.channel_create,
            target_ids={channel.id}
        )

        embed = discord.Embed(
            title="➕ 채널 생성됨",
            description=(
                f"{channel.mention} 채널이 생성되었어요."
            ),
            color=discord.Color.green(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            actor,
            fallback_name="실행자 확인 불가"
        )

        embed.add_field(
            name="채널 ID",
            value=f"`{channel.id}`",
            inline=False
        )

        await send_log(channel.guild, embed)

    except Exception:
        logger.exception(
            "채널 생성 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 채널 삭제
# ============================================================

async def log_channel_delete(
    channel: discord.abc.GuildChannel
):
    if channel.guild is None:
        return

    try:
        settings = get_log_settings(channel.guild.id)

        if not get_setting(settings, "channel_delete"):
            return

        _, actor = await find_audit_log_entry(
            channel.guild,
            actions=discord.AuditLogAction.channel_delete,
            target_ids={channel.id}
        )

        embed = discord.Embed(
            title="🗑️ 채널 삭제됨",
            description=(
                f"`{channel.name}` 채널이 삭제되었어요."
            ),
            color=discord.Color.red(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            actor,
            fallback_name="실행자 확인 불가"
        )

        embed.add_field(
            name="채널 ID",
            value=f"`{channel.id}`",
            inline=False
        )

        await send_log(channel.guild, embed)

    except Exception:
        logger.exception(
            "채널 삭제 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 채널 권한 변경
# ============================================================

async def log_channel_permission_update(
    before: discord.abc.GuildChannel,
    after: discord.abc.GuildChannel
):
    if before.guild is None:
        return

    try:
        guild = before.guild
        settings = get_log_settings(guild.id)

        if not get_setting(
            settings,
            "channel_permissions_update"
        ):
            return

        before_overwrites = get_overwrite_snapshot(before)
        after_overwrites = get_overwrite_snapshot(after)

        changed_targets = []

        all_target_ids = (
            set(before_overwrites)
            | set(after_overwrites)
        )

        for target_id in all_target_ids:
            before_data = before_overwrites.get(target_id)
            after_data = after_overwrites.get(target_id)

            before_target = (
                before_data[0]
                if before_data is not None
                else None
            )

            after_target = (
                after_data[0]
                if after_data is not None
                else None
            )

            before_overwrite = (
                before_data[1]
                if before_data is not None
                else None
            )

            after_overwrite = (
                after_data[1]
                if after_data is not None
                else None
            )

            if (
                before_overwrite is not None
                and after_overwrite is not None
                and before_overwrite == after_overwrite
            ):
                continue

            changed_targets.append(
                (
                    target_id,
                    after_target or before_target,
                    before_overwrite,
                    after_overwrite
                )
            )

        if not changed_targets:
            return

        _, actor = await find_audit_log_entry(
            guild,
            actions=[
                discord.AuditLogAction.overwrite_create,
                discord.AuditLogAction.overwrite_update,
                discord.AuditLogAction.overwrite_delete,
            ],
            target_ids={after.id},
            max_age_seconds=30,
            retry_count=5,
            retry_delay=0.5
        )

        embed = discord.Embed(
            title="🔐 채널 권한 변경됨",
            description=(
                f"{after.mention} 채널의 권한이 변경되었어요."
            ),
            color=discord.Color.gold(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            actor,
            fallback_name="실행자 확인 불가"
        )

        for (
            target_id,
            target,
            before_overwrite,
            after_overwrite
        ) in changed_targets:
            target_name = format_permission_target(
                target=target,
                target_id=target_id,
                guild=guild
            )

            if before_overwrite is None:
                change_text = format_new_overwrite(
                    after_overwrite
                )

            elif after_overwrite is None:
                change_text = (
                    "권한 덮어쓰기가 삭제되었어요."
                )

            else:
                change_text = (
                    format_existing_overwrite_change(
                        before_overwrite,
                        after_overwrite
                    )
                )

            embed.add_field(
                name=f"대상: {target_name}",
                value=change_text,
                inline=False
            )

        embed.add_field(
            name="채널 ID",
            value=f"`{after.id}`",
            inline=False
        )

        await send_log(guild, embed)

    except Exception:
        logger.exception(
            "채널 권한 변경 로그 처리 중 오류가 발생했습니다."
        )


# ============================================================
# 채널 위치 변경
# ============================================================

def queue_channel_position_change(
    before: discord.abc.GuildChannel,
    after: discord.abc.GuildChannel
):
    guild_id = before.guild.id

    changes = _pending_channel_position_changes.setdefault(
        guild_id,
        {}
    )

    if after.id in changes:
        first_position, _ = changes[after.id]

        changes[after.id] = (
            first_position,
            after.position
        )
    else:
        changes[after.id] = (
            before.position,
            after.position
        )

    old_task = _channel_position_flush_tasks.get(guild_id)

    if old_task and not old_task.done():
        old_task.cancel()

    _channel_position_flush_tasks[guild_id] = asyncio.create_task(
        flush_channel_position_changes(before.guild)
    )


def guess_moved_channel_id(
    changes: dict[int, tuple[int, int]]
) -> int | None:
    if not changes:
        return None

    deltas = {
        channel_id: abs(after - before)
        for channel_id, (before, after) in changes.items()
    }

    max_delta = max(deltas.values())

    if max_delta == 0:
        return None

    candidates = [
        channel_id
        for channel_id, delta in deltas.items()
        if delta == max_delta
    ]

    if len(candidates) != 1:
        return None

    return candidates[0]


async def flush_channel_position_changes(
    guild: discord.Guild
):
    try:
        await asyncio.sleep(
            CHANNEL_POSITION_DEBOUNCE_SECONDS
        )

        changes = _pending_channel_position_changes.pop(
            guild.id,
            {}
        )

        if not changes:
            return

        settings = get_log_settings(guild.id)

        if not get_setting(settings, "channel_update"):
            return

        channel_ids = set(changes)

        entry, actor = await find_audit_log_entry(
            guild,
            actions=discord.AuditLogAction.channel_update,
            target_ids=channel_ids,
            max_age_seconds=30,
            retry_count=5,
            retry_delay=0.6
        )

        moved_channel_id = None

        if entry is not None:
            audit_target_id = get_audit_target_id(entry)

            if audit_target_id in channel_ids:
                moved_channel_id = audit_target_id

        if moved_channel_id is None:
            moved_channel_id = guess_moved_channel_id(changes)

        moved_channel = (
            guild.get_channel(moved_channel_id)
            if moved_channel_id is not None
            else None
        )

        affected_channels = []

        for channel_id, (
            before_position,
            after_position
        ) in changes.items():
            if channel_id == moved_channel_id:
                continue

            affected_channels.append(
                (
                    channel_id,
                    before_position,
                    after_position
                )
            )

        affected_channels.sort(
            key=lambda item: item[2]
        )

        if moved_channel_id in changes:
            moved_before, moved_after = changes[
                moved_channel_id
            ]

            moved_name = (
                moved_channel.mention
                if moved_channel is not None
                else f"`채널 {moved_channel_id}`"
            )

            moved_text = (
                f"{moved_name}\n"
                f"`{moved_before}` → `{moved_after}`"
            )
        else:
            moved_text = "확인할 수 없음"

        embed = discord.Embed(
            title="↕️ 채널 순서 변경됨",
            description=(
                f"영향받은 채널 수: {len(changes)}개"
            ),
            color=discord.Color.orange(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            actor,
            fallback_name="실행자 확인 불가"
        )

        embed.add_field(
            name="📌 실제로 이동한 채널",
            value=moved_text,
            inline=False
        )

        if affected_channels:
            lines = []

            for (
                channel_id,
                before_position,
                after_position
            ) in affected_channels:
                channel = guild.get_channel(channel_id)

                channel_name = (
                    channel.mention
                    if channel is not None
                    else f"`채널 {channel_id}`"
                )

                lines.append(
                    f"{channel_name}: "
                    f"`{before_position}` → `{after_position}`"
                )

            for index in range(0, len(lines), 20):
                embed.add_field(
                    name=(
                        "영향받은 채널"
                        if index == 0
                        else "영향받은 채널 계속"
                    ),
                    value="\n".join(
                        lines[index:index + 20]
                    ),
                    inline=False
                )
        else:
            embed.add_field(
                name="영향받은 채널",
                value="없음",
                inline=False
            )

        await send_log(guild, embed)

    except asyncio.CancelledError:
        return

    except Exception:
        logger.exception(
            "채널 위치 변경 요약 로그 처리 중 오류가 발생했습니다."
        )

    finally:
        current_task = _channel_position_flush_tasks.get(guild.id)

        if current_task is asyncio.current_task():
            _channel_position_flush_tasks.pop(guild.id, None)


# ============================================================
# 채널 정보 변경
# ============================================================

async def log_channel_update(
    before: discord.abc.GuildChannel,
    after: discord.abc.GuildChannel
):
    if before.guild is None:
        return

    try:
        guild = before.guild
        settings = get_log_settings(guild.id)

        if not get_setting(settings, "channel_update"):
            return

        # 채널 권한 변경은 별도 로그로 처리합니다.
        await log_channel_permission_update(
            before,
            after
        )

        # 채널 위치 변경은 요약 로그로 처리합니다.
        if before.position != after.position:
            queue_channel_position_change(
                before,
                after
            )

        changes = []

        if before.name != after.name:
            changes.append(
                (
                    "이름",
                    f"`{before.name}` → `{after.name}`"
                )
            )

        before_topic = getattr(before, "topic", None)
        after_topic = getattr(after, "topic", None)

        if before_topic != after_topic:
            changes.append(
                (
                    "주제",
                    f"{before_topic or '(없음)'} → "
                    f"{after_topic or '(없음)'}"
                )
            )

        before_category_id = getattr(
            before,
            "category_id",
            None
        )

        after_category_id = getattr(
            after,
            "category_id",
            None
        )

        if before_category_id != after_category_id:
            before_category = getattr(
                before,
                "category",
                None
            )

            after_category = getattr(
                after,
                "category",
                None
            )

            before_name = (
                before_category.name
                if before_category
                else "(없음)"
            )

            after_name = (
                after_category.name
                if after_category
                else "(없음)"
            )

            changes.append(
                (
                    "카테고리",
                    f"`{before_name}` → `{after_name}`"
                )
            )

        # 위치·권한만 변경된 경우에는 전용 로그가 처리합니다.
        if not changes:
            return

        _, actor = await find_audit_log_entry(
            guild,
            actions=discord.AuditLogAction.channel_update,
            target_ids={after.id},
            max_age_seconds=30,
            retry_count=5,
            retry_delay=0.5
        )

        embed = discord.Embed(
            title="🔧 채널 정보 변경됨",
            description=(
                f"{after.mention} 채널의 정보가 변경되었어요."
            ),
            color=discord.Color.orange(),
            timestamp=utc_now()
        )

        set_actor(
            embed,
            actor,
            fallback_name="실행자 확인 불가"
        )

        for name, value in changes:
            embed.add_field(
                name=name,
                value=value,
                inline=False
            )

        embed.add_field(
            name="채널 ID",
            value=f"`{after.id}`",
            inline=False
        )

        await send_log(guild, embed)

    except Exception:
        logger.exception(
            "채널 정보 변경 로그 처리 중 오류가 발생했습니다."
        )