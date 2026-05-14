import discord
import sqlite3

LOG_DB_PATH = "log_channel.db"

def get_log_channel_id(guild_id: int):
    conn = sqlite3.connect(LOG_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT channel_id FROM log_channel WHERE guild_id = ?", (guild_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return int(row[0])
    return None

async def show_server_settings(interaction: discord.Interaction):
    # 관리자 권한 검사
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "⚠️ 이 명령어는 서버 관리자만 사용할 수 있습니다.",
            ephemeral=True
        )
        return

    guild_id = interaction.guild.id
    log_channel_id = get_log_channel_id(guild_id)
    log_channel = interaction.guild.get_channel(log_channel_id) if log_channel_id else None

    embed = discord.Embed(
        title="이 서버의 설정",
        color=discord.Color.green(),
    )
    embed.add_field(
        name="로그 채널",
        value=log_channel.mention if log_channel else "설정 안됨",
        inline=False,
    )
    await interaction.response.send_message(embed=embed)

settings_slash_cmd = discord.app_commands.Command(
    name="설정",
    description="이 서버의 로그 채널 설정을 보여줍니다.",
    callback=show_server_settings
)