import datetime

import discord

from .log_settings_db import get_log_channel_id


LOG_TYPE_NAMES: dict[str, str] = {
    "message_delete": "💬 메시지 삭제",
    "message_edit": "✏️ 메시지 수정",

    "member_join": "➡️ 멤버 입장",
    "member_remove": "⬅️ 멤버 퇴장",
    "member_role_update": "👤 멤버 역할 변경",

    "member_kick": "👢 멤버 추방",
    "member_ban": "🔨 멤버 차단",
    "member_unban": "🔓 차단 해제",

    "role_update": "⚙️ 역할 정보 변경",
    "role_permissions_update": "🔐 역할 권한 변경",
    "role_create": "➕ 역할 생성",
    "role_delete": "🗑️ 역할 삭제",

    "channel_create": "➕ 채널 생성",
    "channel_delete": "🗑️ 채널 삭제",
    "channel_update": "🔧 채널 정보 변경",
    "channel_permissions_update": "🔐 채널 권한 변경",
}


async def log_settings_change(
    guild: discord.Guild,
    user: discord.User | discord.Member,
    changes: dict[str, tuple[bool, bool]]
):
    log_channel_id = get_log_channel_id(guild.id)

    if not log_channel_id:
        return

    log_channel = guild.get_channel(log_channel_id)

    if log_channel is None:
        return

    if not changes:
        return

    embed = discord.Embed(
        title="⚙️ 로그 설정 변경",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    try:
        avatar_url = user.display_avatar.url
    except Exception:
        avatar_url = None

    if avatar_url:
        embed.set_author(
            name=str(user),
            icon_url=avatar_url
        )
    else:
        embed.set_author(name=str(user))

    change_lines = []

    for key, (
        old_value,
        new_value
    ) in changes.items():
        log_name = LOG_TYPE_NAMES.get(key, key)
        status = "✅ 활성화" if new_value else "❌ 비활성화"

        change_lines.append(
            f"{log_name}: {status}"
        )

    embed.add_field(
        name="변경사항",
        value="\n".join(change_lines),
        inline=False
    )

    embed.set_footer(
        text=f"작업자 ID: {user.id}"
    )

    try:
        await log_channel.send(embed=embed)

    except discord.Forbidden:
        return

    except discord.HTTPException:
        return