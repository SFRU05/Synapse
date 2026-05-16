import discord
from discord import app_commands
from .log_settings_db import get_log_settings, update_all_log_settings, set_log_channel, get_log_channel_id
from .log_settings_change import log_settings_change

LOG_TYPES = {
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


class LogSettingsView(discord.ui.View):
    def __init__(self, guild_id: int, current_settings: dict):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.settings = current_settings.copy()

        # Select 메뉴 생성
        options = [
            discord.SelectOption(
                label=label,
                value=key,
                emoji=label.split()[0],
                default=current_settings.get(key, True)
            )
            for key, label in LOG_TYPES.items()
        ]

        select = discord.ui.Select(
            placeholder="로그 종류를 선택하세요",
            min_values=0,
            max_values=len(LOG_TYPES),
            options=options
        )
        select.callback = self.select_logs
        self.add_item(select)

    async def select_logs(self, interaction: discord.Interaction):
        select = interaction.data['values']

        # 이전 설정과 변경된 설정 비교
        changed = {}
        for key in LOG_TYPES.keys():
            old_value = self.settings.get(key, True)
            new_value = key in select
            if old_value != new_value:
                changed[key] = (old_value, new_value)

        # 선택된 항목들을 True로, 아닌 것들을 False로 설정
        for key in LOG_TYPES.keys():
            self.settings[key] = key in select

        # 설정 저장
        update_all_log_settings(self.guild_id, self.settings)

        # 현재 선택된 로그들을 표시
        if select:
            selected = [LOG_TYPES[k] for k in select]
            embed = discord.Embed(
                title="✅ 로그 설정 저장됨",
                description="다음 로그들이 활성화되었습니다:\n" + "\n".join(selected),
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="✅ 로그 설정 저장됨",
                description="모든 로그가 비활성화되었습니다.",
                color=discord.Color.green(),
            )

        await interaction.response.edit_message(embed=embed)

        # 로그 채널에 변경사항 기록
        if changed:
            await log_settings_change(interaction.guild, interaction.user, changed)


@app_commands.command(name="로그채널", description="서버 로그용 채널을 지정합니다 (관리자만 가능)")
@app_commands.describe(channel="로그를 보낼 텍스트 채널")
async def setlog_slash(
        interaction: discord.Interaction,
        channel: discord.TextChannel
):
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="❌ 권한 부족",
            description="관리자 권한이 필요합니다.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    set_log_channel(interaction.guild.id, channel.id)
    embed = discord.Embed(
        title="✅ 로그 채널 설정 완료",
        description=f"{channel.mention} 채널이 로그 채널로 지정되었습니다.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@app_commands.command(name="로그설정", description="로그 종류별 설정을 관리합니다 (관리자만 가능)")
async def logsettings_slash(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="❌ 권한 부족",
            description="관리자 권한이 필요합니다.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    current_settings = get_log_settings(interaction.guild.id)
    log_channel_id = get_log_channel_id(interaction.guild.id)

    embed = discord.Embed(
        title="📋 로그 설정 관리",
        description="활성화할 로그 종류를 선택하세요.\n아래의 드롭다운에서 로그 종류를 선택하세요.",
        color=discord.Color.blurple(),
    )

    # 로그 채널 표시
    if log_channel_id:
        log_channel = interaction.guild.get_channel(log_channel_id)
        if log_channel:
            embed.add_field(name="로그 채널", value=log_channel.mention, inline=False)
        else:
            embed.add_field(name="로그 채널", value="설정되지 않음 (채널이 삭제됨)", inline=False)
    else:
        embed.add_field(name="로그 채널", value="설정되지 않음 - `/로그채널` 명령어로 설정하세요", inline=False)

    # 현재 활성화된 로그 표시
    enabled = [LOG_TYPES[k] for k, v in current_settings.items() if v]
    embed.add_field(
        name="현재 활성화된 로그",
        value="\n".join(enabled) if enabled else "없음",
        inline=False
    )

    view = LogSettingsView(interaction.guild.id, current_settings)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)