import discord
from discord import app_commands
import sqlite3
from datetime import datetime, timedelta, timezone

# 한국 시간대(KST) 정의 (UTC+9)
KST = timezone(timedelta(hours=9))

def ensure_warning_db():
    """경고 데이터베이스 생성"""
    conn = sqlite3.connect("warnings.db")
    cursor = conn.cursor()

    # 경고 테이블
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS warnings
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       guild_id
                       INTEGER
                       NOT
                       NULL,
                       member_id
                       INTEGER
                       NOT
                       NULL,
                       moderator_id
                       INTEGER
                       NOT
                       NULL,
                       reason
                       TEXT,
                       timestamp
                       DATETIME
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   """)

    # 서버별 경고 설정 테이블
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS warning_settings
                   (
                       guild_id
                       INTEGER
                       PRIMARY
                       KEY,
                       expire_days
                       INTEGER
                       DEFAULT
                       30,
                       timeout_count
                       INTEGER
                       DEFAULT
                       3,
                       timeout_hours
                       INTEGER
                       DEFAULT
                       24,
                       ban_count
                       INTEGER
                       DEFAULT
                       5
                   )
                   """)

    conn.commit()
    conn.close()


def get_warning_settings(guild_id: int) -> dict:
    """서버의 경고 설정 조회 (없으면 기본값 반환)"""
    conn = sqlite3.connect("warnings.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT expire_days, timeout_count, timeout_hours, ban_count FROM warning_settings WHERE guild_id = ?",
        (guild_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        return {
            "expire_days": 30,
            "timeout_count": 3,
            "timeout_hours": 24,
            "ban_count": 5
        }

    return {
        "expire_days": result[0],
        "timeout_count": result[1],
        "timeout_hours": result[2],
        "ban_count": result[3]
    }


def set_warning_settings(guild_id: int, expire_days: int, timeout_count: int, timeout_hours: int,
                         ban_count: int) -> bool:
    """서버의 경고 설정 저장"""
    conn = sqlite3.connect("warnings.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO warning_settings (guild_id, expire_days, timeout_count, timeout_hours, ban_count)
        VALUES (?, ?, ?, ?, ?)
    """, (guild_id, expire_days, timeout_count, timeout_hours, ban_count))

    conn.commit()
    conn.close()
    return True


def add_warning(guild_id: int, member_id: int, moderator_id: int, reason: str) -> int:
    """경고 추가"""
    conn = sqlite3.connect("warnings.db")
    cursor = conn.cursor()

    cursor.execute("""
                   INSERT INTO warnings (guild_id, member_id, moderator_id, reason)
                   VALUES (?, ?, ?, ?)
                   """, (guild_id, member_id, moderator_id, reason))

    warning_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return warning_id


def get_warnings(guild_id: int, member_id: int) -> list:
    """특정 멤버의 전체 경고 조회"""
    conn = sqlite3.connect("warnings.db")
    cursor = conn.cursor()

    cursor.execute("""
                   SELECT id, moderator_id, reason, timestamp
                   FROM warnings
                   WHERE guild_id = ? AND member_id = ?
                   ORDER BY timestamp DESC
                   """, (guild_id, member_id))

    warnings = cursor.fetchall()
    conn.close()
    return warnings


def get_active_warnings(guild_id: int, member_id: int) -> list:
    """만료되지 않은 유효한 경고만 조회 (0일 때는 만료 없음 처리)"""
    conn = sqlite3.connect("warnings.db")
    cursor = conn.cursor()

    settings = get_warning_settings(guild_id)
    expire_days = settings["expire_days"]

    if expire_days > 0:
        expire_date = datetime.now(timezone.utc) - timedelta(days=expire_days)
        cursor.execute("""
                       SELECT id, moderator_id, reason, timestamp
                       FROM warnings
                       WHERE guild_id = ? AND member_id = ? AND timestamp > ?
                       ORDER BY timestamp DESC
                       """, (guild_id, member_id, expire_date.strftime("%Y-%m-%d %H:%M:%S")))
    else:
        cursor.execute("""
                       SELECT id, moderator_id, reason, timestamp
                       FROM warnings
                       WHERE guild_id = ? AND member_id = ?
                       ORDER BY timestamp DESC
                       """, (guild_id, member_id))

    warnings = cursor.fetchall()
    conn.close()
    return warnings


def remove_warning(warning_id: int) -> bool:
    """특정 경고 삭제"""
    conn = sqlite3.connect("warnings.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM warnings WHERE id = ?", (warning_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def clear_warnings(guild_id: int, member_id: int) -> int:
    """멤버의 모든 경고 삭제"""
    conn = sqlite3.connect("warnings.db")
    cursor = conn.cursor()

    cursor.execute("""
                   DELETE
                   FROM warnings
                   WHERE guild_id = ?
                     AND member_id = ?
                   """, (guild_id, member_id))

    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


# ==========================================
# 2. UI 컴포넌트 (Buttons, Modals, Views)
# ==========================================

class WarningConfirmView(discord.ui.View):
    """경고 부여 확인 버튼"""

    def __init__(self, member: discord.Member, reason: str, moderator: discord.Member):
        super().__init__(timeout=15)
        self.member = member
        self.reason = reason
        self.moderator = moderator
        self.result = None

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.moderator.id

    @discord.ui.button(label="✅ 예", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = "confirm"
        self.stop()
        await interaction.response.defer(ephemeral=False)

    @discord.ui.button(label="❌ 아니요", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = "cancel"
        self.stop()
        await interaction.response.defer(ephemeral=True)


class WarningSettingsModal(discord.ui.Modal, title="경고 시스템 설정"):
    expire_days = discord.ui.TextInput(label="경고 만료 기간 (일) - 비움: 비활성화", placeholder="예) 30", min_length=0, max_length=3,
                                       required=False)
    timeout_count = discord.ui.TextInput(label="타임아웃 경고 수 - 비움: 비활성화", placeholder="예) 2", min_length=0, max_length=2,
                                         required=False)
    timeout_hours = discord.ui.TextInput(label="타임아웃 시간 (시간) - 비움: 비활성화", placeholder="예) 24", min_length=0, max_length=3,
                                         required=False)
    ban_count = discord.ui.TextInput(label="밴 경고 수 - 비움: 비활성화", placeholder="예) 5", min_length=0, max_length=2,
                                     required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            expire = int(self.expire_days.value) if self.expire_days.value else 0
            timeout = int(self.timeout_count.value) if self.timeout_count.value else 0
            timeout_hrs = int(self.timeout_hours.value) if self.timeout_hours.value else 0
            ban = int(self.ban_count.value) if self.ban_count.value else 0

            if timeout == 0:
                timeout_hrs = 0

            if expire < 0 or timeout < 0 or timeout_hrs < 0 or ban < 0:
                await interaction.response.send_message("음수는 입력할 수 없습니다.", ephemeral=True)
                return

            if timeout_hrs > 2016:
                await interaction.response.send_message("타임아웃 시간은 2016시간(84일) 이하여야 합니다.", ephemeral=True)
                return

            if timeout > 0 and timeout_hrs == 0:
                await interaction.response.send_message("타임아웃 횟수와 시간을 같이 설정해야 해요.", ephemeral=True)
                return

            if ban != 0 and timeout != 0 and ban <= timeout:
                await interaction.response.send_message("밴 경고 수는 타임아웃 경고 수보다 커야 해요.", ephemeral=True)
                return

            set_warning_settings(interaction.guild_id, expire, timeout, timeout_hrs, ban)

            embed = discord.Embed(title="✅ 설정 저장 완료", description="경고 시스템 설정이 저장되었어요.", color=discord.Color.green())
            embed.add_field(name="경고 만료 기간", value=f"`{expire}일`" if expire > 0 else "❌ 비활성화", inline=True)
            embed.add_field(name="타임아웃 경고 수", value=f"`{timeout}회`" if timeout > 0 else "❌ 비활성화", inline=True)
            if timeout > 0:
                embed.add_field(name="타임아웃 시간", value=f"`{timeout_hrs}시간`", inline=True)
            embed.add_field(name="밴 경고 수", value=f"`{ban}회`" if ban > 0 else "❌ 비활성화", inline=True)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.response.send_message("올바르지 않은 값이에요! 숫자만 입력해주세요.", ephemeral=True)


class SettingsButtonView(discord.ui.View):

    def __init__(self, current_settings: dict):
        super().__init__(timeout=None)
        self.current_settings = current_settings

    @discord.ui.button(label="설정 변경", style=discord.ButtonStyle.primary)
    async def change_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WarningSettingsModal()
        modal.expire_days.default = str(self.current_settings['expire_days']) if self.current_settings[
                                                                                     'expire_days'] > 0 else ""
        modal.timeout_count.default = str(self.current_settings['timeout_count']) if self.current_settings[
                                                                                         'timeout_count'] > 0 else ""
        modal.timeout_hours.default = str(self.current_settings['timeout_hours']) if self.current_settings[
                                                                                         'timeout_hours'] > 0 else ""
        modal.ban_count.default = str(self.current_settings['ban_count']) if self.current_settings[
                                                                                 'ban_count'] > 0 else ""
        await interaction.response.send_modal(modal)


class WarningManageView(discord.ui.View):

    def __init__(self, member: discord.Member, all_warnings: list, active_warnings: list):
        super().__init__(timeout=60)
        self.member = member
        self.all_warnings = all_warnings
        self.active_ids = [w[0] for w in active_warnings]
        self.current_page = 0
        self.per_page = 5
        self.max_page = (len(all_warnings) - 1) // self.per_page
        self.update_components()

    def update_components(self):
        self.clear_items()

        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_warnings = self.all_warnings[start_idx:end_idx]

        embed = discord.Embed(
            title=f"⚠️ {self.member.name}님의 경고 기록",
            description=f"전체 경고: **{len(self.all_warnings)}회** | 유효한 경고: **{len(self.active_ids)}회**\n(페이지: {self.current_page + 1}/{self.max_page + 1})",
            color=discord.Color.orange()
        )

        options = [
            discord.SelectOption(label="🗑️ 모든 경고 삭제", value="all", description="이 유저의 모든 경고 기록을 초기화해요.", emoji="🗑️")]

        for i, (warning_id, moderator_id, reason, timestamp) in enumerate(page_warnings, start=start_idx + 1):
            is_active = "✅" if warning_id in self.active_ids else "❌"

            dt_utc = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            dt_kst = dt_utc.astimezone(KST)

            formatted_time = dt_kst.strftime("%Y-%m-%d %H:%M:%S")
            unix_time = int(dt_utc.timestamp())

            embed.add_field(
                name=f"{is_active} 경고 #{i} (ID: {warning_id})",
                value=f"사유: {reason}\n중재자: <@{moderator_id}>\n부여 시각: {formatted_time} (<t:{unix_time}:R>)",
                inline=False
            )

            options.append(
                discord.SelectOption(
                    label=f"경고 #{i}",
                    value=str(warning_id),
                    description=f"사유: {reason[:30]}... | {formatted_time}",
                    emoji="⚠️"
                )
            )

        self.add_item(WarningSelect(options))

        if self.max_page > 0:
            prev_btn = discord.ui.Button(label="◀️ 이전", style=discord.ButtonStyle.secondary,
                                         disabled=(self.current_page == 0))
            prev_btn.callback = self.prev_page_callback
            self.add_item(prev_btn)

            next_btn = discord.ui.Button(label="▶️ 다음", style=discord.ButtonStyle.secondary,
                                         disabled=(self.current_page == self.max_page))
            next_btn.callback = self.next_page_callback
            self.add_item(next_btn)

        return embed

    async def prev_page_callback(self, interaction: discord.Interaction):
        self.current_page -= 1
        embed = self.update_components()
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        self.current_page += 1
        embed = self.update_components()
        await interaction.response.edit_message(embed=embed, view=self)


class WarningSelect(discord.ui.Select):
    # 경고 관리 내 개별/전체 삭제 드롭다운 메뉴

    def __init__(self, options):
        super().__init__(placeholder="삭제할 경고를 선택하세요", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ 경고를 삭제할 권한이 없어요.", ephemeral=True)
            return

        selected_value = self.values[0]
        member = self.view.member

        if selected_value == "all":
            count = clear_warnings(interaction.guild_id, member.id)
            embed = discord.Embed(title="✅ 모든 경고 삭제 완료", description=f"{member.mention} 님의 모든 경고 **{count}개**를 삭제했어요.",
                                  color=discord.Color.green())
        else:
            warning_id = int(selected_value)
            if remove_warning(warning_id):
                embed = discord.Embed(title="✅ 경고 삭제 완료",
                                      description=f"{member.mention} 님의 경고 (ID: {warning_id})를 삭제했어요.",
                                      color=discord.Color.green())
            else:
                embed = discord.Embed(title="❌ 오류", description="해당 경고를 찾을 수 없거나 이미 삭제되었어요.",
                                      color=discord.Color.red())

        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.view.stop()

warning_cmd = app_commands.Group(name="경고", description="경고 시스템")


@warning_cmd.command(name="부여", description="멤버에게 경고를 부여합니다")
@app_commands.describe(member="경고할 멤버를 선택하세요", reason="경고 사유 (기본값: 사유 없음)")
async def give_warning(interaction: discord.Interaction, member: discord.Member, reason: str = "사유 없음"):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("작업을 수행할 권한이 없어요.", ephemeral=True)
        return

    if member.bot or member == interaction.user:
        await interaction.response.send_message("대상이 올바르지 않아요. 정확하게 입력해주세요.", ephemeral=True)
        return

    embed = discord.Embed(title="경고 확인", description=f"{member.mention} 님에게 경고를 부여할까요?", color=discord.Color.red())
    embed.add_field(name="사유", value=reason, inline=False)
    embed.set_footer(text="15초 내에 선택해주세요.")

    view = WarningConfirmView(member, reason, interaction.user)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    await view.wait()

    if view.result == "confirm":
        try:
            warning_id = add_warning(interaction.guild_id, member.id, interaction.user.id, reason)
            active_warnings = get_active_warnings(interaction.guild_id, member.id)
            warnings_count = len(active_warnings)
            settings = get_warning_settings(interaction.guild_id)
            now_unix = int(datetime.now(timezone.utc).timestamp())

            try:
                dm_embed = discord.Embed(title="⚠️ 경고가 부여되었어요.",
                                         description=f"**{interaction.guild.name}** 서버에서 경고를 받았어요.",
                                         color=discord.Color.red())
                dm_embed.add_field(name="사유", value=reason, inline=False)
                dm_embed.add_field(name="누적 경고", value=f"`{warnings_count}`회", inline=False)
                dm_embed.add_field(name="부여 시각", value=f"<t:{now_unix}:F>", inline=False)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass

            public_embed = discord.Embed(title="⚠️ 경고 부여", description=f"{member.mention} 님이 경고를 받았어요.",
                                         color=discord.Color.orange())
            public_embed.add_field(name="사유", value=reason, inline=False)
            public_embed.add_field(name="누적 경고", value=f"`{warnings_count}`회", inline=False)
            public_embed.add_field(name="부여 시각", value=f"<t:{now_unix}:F>", inline=False)
            await interaction.channel.send(embed=public_embed)

            success_msg = f"✅ {member.mention} 님에게 경고를 부여했어요. (누적: {warnings_count}회)"

            if settings["ban_count"] > 0 and warnings_count >= settings["ban_count"]:
                await member.ban(reason="경고 누적 밴")
                await interaction.channel.send(f"🔨 {member.mention} 님이 경고 누적으로 차단되었어요.")
                success_msg += f"\n🔨 경고 {settings['ban_count']}회 누적으로 자동 차단되었어요."

            elif settings["timeout_count"] > 0 and warnings_count >= settings["timeout_count"]:
                await member.timeout(timedelta(hours=settings["timeout_hours"]), reason="경고 누적 타임아웃")
                await interaction.channel.send(f"⏱️ {member.mention} 님이 {settings['timeout_hours']}시간 타임아웃되었어요.")
                success_msg += f"\n⏱️ 경고 {settings['timeout_count']}회 누적으로 자동 타임아웃되었어요. ({settings['timeout_hours']}시간)"

            await interaction.edit_original_response(content=success_msg, embed=None, view=None)

        except Exception as e:
            await interaction.edit_original_response(content=f"❌ 오류 발생: {e}", embed=None, view=None)
    else:
        await interaction.edit_original_response(content="작업이 취소되었어요.", embed=None, view=None)


@warning_cmd.command(name="관리", description="멤버의 경고를 조회하고 삭제해요.")
@app_commands.describe(member="관리할 멤버를 선택하세요")
async def manage_warnings(interaction: discord.Interaction, member: discord.Member):
    all_warnings = get_warnings(interaction.guild_id, member.id)
    active_warnings = get_active_warnings(interaction.guild_id, member.id)

    if not all_warnings:
        await interaction.response.send_message("조회된 경고 기록이 없어요.", ephemeral=True)
        return

    view = WarningManageView(member, all_warnings, active_warnings)
    initial_embed = view.update_components()

    await interaction.response.send_message(embed=initial_embed, view=view, ephemeral=True)


@warning_cmd.command(name="설정", description="경고 시스템 설정을 확인해요.")
async def warning_settings(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("권한이 없습니다.", ephemeral=True)
        return

    settings = get_warning_settings(interaction.guild_id)

    embed = discord.Embed(title="⚙️ 경고 시스템 설정", color=discord.Color.blurple())
    embed.add_field(name="경고 만료 기간", value=f"`{settings['expire_days']}일`" if settings['expire_days'] > 0 else "❌ 비활성화",
                    inline=True)
    embed.add_field(name="타임아웃 경고 수",
                    value=f"`{settings['timeout_count']}회`" if settings['timeout_count'] > 0 else "❌ 비활성화", inline=True)

    if settings['timeout_count'] > 0:
        embed.add_field(name="타임아웃 시간", value=f"`{settings['timeout_hours']}시간`", inline=True)

    embed.add_field(name="밴 경고 수", value=f"`{settings['ban_count']}회`" if settings['ban_count'] > 0 else "❌ 비활성화",
                    inline=True)

    if settings['timeout_count'] > 0 or settings['ban_count'] > 0:
        punishments = []
        if settings['timeout_count'] > 0: punishments.append(f"타임아웃({settings['timeout_count']}회)")
        if settings['ban_count'] > 0: punishments.append(f"밴({settings['ban_count']}회)")
        embed.add_field(name="아래와 같이 자동으로 중재돼요.", value=" ➡️ ".join(punishments), inline=False)

    await interaction.response.send_message(embed=embed, view=SettingsButtonView(settings))