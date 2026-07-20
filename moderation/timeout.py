import logging
import re
import traceback
from datetime import timedelta

import discord
from discord import app_commands

logger = logging.getLogger("moderation")

MAX_TIMEOUT_DURATION = timedelta(days=7)

_DURATION_PATTERN = re.compile(
    r"(?:(?P<days>\d+)\s*d)?\s*(?:(?P<hours>\d+)\s*h)?\s*(?:(?P<minutes>\d+)\s*m)?",
    re.IGNORECASE,
)

def parse_duration(raw: str) -> timedelta | None:
    raw = raw.strip().replace(" ", "")
    if not raw:
        return None

    match = _DURATION_PATTERN.fullmatch(raw)
    if not match:
        return None

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)

    if days == 0 and hours == 0 and minutes == 0:
        return None

    return timedelta(days=days, hours=hours, minutes=minutes)


def format_duration(duration: timedelta) -> str:
    """timedelta를 '1일 2시간 3분' 형태의 한국어 문자열로 변환 (0인 단위는 생략)."""
    total_minutes = int(duration.total_seconds() // 60)
    days, remainder = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}일")
    if hours:
        parts.append(f"{hours}시간")
    if minutes or not parts:
        parts.append(f"{minutes}분")
    return " ".join(parts)

class ConfirmView(discord.ui.View):

    def __init__(self, moderator: discord.Member, *, timeout: float = 15):
        super().__init__(timeout=timeout)
        self.moderator = moderator
        self.result: str | None = None  # "confirm" / "cancel" / None(시간초과)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message(
                "이 버튼은 명령어를 실행한 사람만 누를 수 있어요.", ephemeral=True
            )
            return False
        return True

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

def check_moderation_possible(guild: discord.Guild, member: discord.Member) -> str | None:
    bot_member = guild.me

    if member.id == guild.owner_id:
        return "❌ 서버 소유자는 타임아웃할 수 없어요."

    if member.id == bot_member.id:
        return "❌ 저를 타임아웃하시면 안 돼요!!"

    if not bot_member.guild_permissions.moderate_members:
        return "❌ 봇 역할에 타임아웃 권한이 없어요. 서버 설정 → 역할에서 권한을 확인해주세요."

    if member.top_role >= bot_member.top_role:
        return (
            f"❌ **역할 순서 권한 오류가 발생했어요.** {member.mention} 님의 최상위 역할이 "
            f"제 최상위 역할({bot_member.top_role.mention})보다 높거나 같아서 처리할 수 없어요. "
            "서버 설정 → 역할에서 봇 역할을 대상보다 위로 올려주세요."
        )

    return None


async def apply_timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    until: timedelta | None,
    reason: str | None,
) -> tuple[bool, str]:
    try:
        await member.timeout(until, reason=reason)
        return True, ""
    except discord.Forbidden as e:
        logger.error("Forbidden 발생 (member=%s): %s", member, e)
        logger.error(traceback.format_exc())
        return False, "❌ 봇에 타임아웃 권한이 없어요."
    except discord.HTTPException as e:
        logger.error("HTTPException 발생 (member=%s): %s", member, e)
        logger.error(traceback.format_exc())
        return False, "❌ 타임아웃 요청 중 오류가 발생했어요."
    except Exception as e:
        logger.error("알 수 없는 에러 (member=%s): %s: %s", member, type(e).__name__, e)
        logger.error(traceback.format_exc())
        return False, "❌ 알 수 없는 오류가 발생했어요."


def build_embed(title: str, description: str, color: discord.Color, *, reason: str | None = None,
                 moderator: discord.Member | None = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if moderator is not None:
        embed.add_field(name="중재자", value=moderator.mention, inline=True if reason else False)
    if reason is not None:
        embed.add_field(name="사유", value=reason, inline=False)
    return embed


async def run_confirmation_flow(
    interaction: discord.Interaction,
    *,
    confirm_title: str,
    confirm_description: str,
    confirm_color: discord.Color,
    reason: str | None,
    cancel_title: str,
    cancel_description: str,
    timeout_title: str,
    timeout_description: str,
):
    embed = build_embed(confirm_title, confirm_description, confirm_color, reason=reason)
    embed.set_footer(text="15초 내 예 또는 아니요를 눌러주세요.")

    view = ConfirmView(interaction.user)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    await view.wait()

    if view.result == "cancel":
        await interaction.edit_original_response(
            embed=build_embed(cancel_title, cancel_description, discord.Color.light_grey()),
            view=None,
        )
    elif view.result is None:
        await interaction.edit_original_response(
            embed=build_embed(timeout_title, timeout_description, discord.Color.light_grey()),
            view=None,
        )

    return view.result

@app_commands.command(name="타임아웃", description="유저를 일정 시간 타임아웃해요. (예: 1h1m, 2d, 30m, 최대 7d)")
@app_commands.describe(
    member="타임아웃할 멤버를 선택해주세요..",
    duration="타임아웃 시간. 예: 1h1m, 2d, 30m, 1d12h (최대 7d)",
    reason="사유. 기본값: 사유 없음",
)
async def timeout_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    duration: str,
    reason: str = "사유 없음",
):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ 이 명령어를 사용할 권한이 없어요.", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("❌ 본인을 타임아웃할 수 없어요.", ephemeral=True)
        return

    timeout_duration = parse_duration(duration)
    if timeout_duration is None:
        await interaction.response.send_message(
            "❌ 시간 형식이 올바르지 않아요. `1h1m`, `2d`, `30m`, `1d12h30m` 같은 형태로 입력해주세요.",
            ephemeral=True,
        )
        return

    if timeout_duration > MAX_TIMEOUT_DURATION:
        await interaction.response.send_message(
            "❌ 타임아웃은 최대 7일(7d)까지만 설정할 수 있어요.", ephemeral=True
        )
        return

    precheck_error = check_moderation_possible(interaction.guild, member)
    if precheck_error:
        await interaction.response.send_message(precheck_error, ephemeral=True)
        return

    duration_text = format_duration(timeout_duration)

    result = await run_confirmation_flow(
        interaction,
        confirm_title="타임아웃 확인",
        confirm_description=f"{member.mention} 님을 {duration_text} 동안 타임아웃할까요?",
        confirm_color=discord.Color.red(),
        reason=reason,
        cancel_title="타임아웃 요청 취소",
        cancel_description=f"{member.mention} 님에 대한 타임아웃 요청이 취소되었어요.",
        timeout_title="시간 초과",
        timeout_description="15초 내 선택이 없어 타임아웃 요청이 취소되었어요.",
    )

    if result != "confirm":
        return

    success, error_message = await apply_timeout(interaction, member, timeout_duration, reason)

    if success:
        public_embed = build_embed(
            "타임아웃 완료",
            f"{member.mention} 님이 {duration_text} 동안 타임아웃되었어요.",
            discord.Color.green(),
            reason=reason,
            moderator=interaction.user,
        )
        await interaction.channel.send(embed=public_embed)  # 공개
        await interaction.edit_original_response(content="✅ 타임아웃이 수행되었어요.", embed=None, view=None)
    else:
        await interaction.edit_original_response(content=error_message, embed=None, view=None)

@app_commands.command(name="pardon", description="유저의 타임아웃을 해제합니다. (확인 버튼)")
@app_commands.describe(
    member="타임아웃을 해제할 멤버를 선택해주세요.",
)
async def pardon_slash(
    interaction: discord.Interaction,
    member: discord.Member,
):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ 이 명령어를 사용할 권한이 없어요.", ephemeral=True)
        return

    precheck_error = check_moderation_possible(interaction.guild, member)
    if precheck_error:
        await interaction.response.send_message(precheck_error, ephemeral=True)
        return

    result = await run_confirmation_flow(
        interaction,
        confirm_title="타임아웃 해제 확인",
        confirm_description=f"{member.mention} 님의 타임아웃을 해제할까요?",
        confirm_color=discord.Color.orange(),
        reason=None,
        cancel_title="타임아웃 해제 요청 취소",
        cancel_description=f"{member.mention} 님에 대한 타임아웃 해제 요청이 취소되었어요.",
        timeout_title="시간 초과",
        timeout_description="15초 내 선택이 없어 타임아웃 해제 요청이 취소되었어요.",
    )

    if result != "confirm":
        return

    success, error_message = await apply_timeout(interaction, member, None, None)

    if success:
        public_embed = build_embed(
            "타임아웃 해제 완료",
            f"{member.mention} 님의 타임아웃이 해제되었어요.",
            discord.Color.green(),
            moderator=interaction.user,
        )
        await interaction.channel.send(embed=public_embed)
        await interaction.edit_original_response(content="✅ 타임아웃 해제가 수행되었어요.", embed=None, view=None)
    else:
        await interaction.edit_original_response(
            content=error_message.replace("타임아웃 권한", "타임아웃 해제 권한"),
            embed=None,
            view=None,
        )