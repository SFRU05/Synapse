import datetime
import discord
from .log_settings_db import get_log_channel_id

LOG_TYPE_NAMES = {
    "message_delete": "💬 메시지 삭제",
    "message_edit": "✏️ 메시지 수정",
    "member_join": "➡️ 멤버 입장",
    "member_remove": "⬅️ 멤버 퇴장",
    "member_role_update": "👤 멤버 역할 변경",
    "role_update": "⚙️ 역할 정보 변경",
    "role_create": "➕ 역할 생성",
    "role_delete": "🗑️ 역할 삭제",
    "channel_create": "➕ 채널 생성",
    "channel_delete": "🗑️ 채널 삭제",
    "channel_update": "🔧 채널 정보 변경",
}


# 로그 설정 변경 기록
async def log_settings_change(guild: discord.Guild, user: discord.User, changes: dict):
    """로그 설정 변경사항을 기록"""
    log_channel_id = get_log_channel_id(guild.id)
    if not log_channel_id:
        return

    log_channel = guild.get_channel(log_channel_id)
    if not log_channel:
        return

    embed = discord.Embed(
        title="⚙️ 로그 설정 변경",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now()
    )
    embed.set_author(name=str(user), icon_url=user.display_avatar.url)

    # 변경 사항 표시
    change_text = []
    for key, (old_value, new_value) in changes.items():
        log_name = LOG_TYPE_NAMES.get(key, key)
        status = "✅ 활성화" if new_value else "❌ 비활성화"
        change_text.append(f"{log_name}: {status}")

    embed.add_field(
        name="변경사항",
        value="\n".join(change_text),
        inline=False
    )
    embed.set_footer(text=f"ID: {user.id}")

    await log_channel.send(embed=embed)