import logging
import traceback

import discord
from discord import app_commands

logger = logging.getLogger("moderation")

class ConfirmView(discord.ui.View):

    def __init__(self, moderator: discord.Member, *, timeout: float = 15):
        super().__init__(timeout=timeout)
        self.moderator = moderator
        self.result: str | None = None

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

def build_embed(
    title: str,
    description: str,
    color: discord.Color,
    *,
    reason: str | None = None,
    moderator: discord.Member | None = None,
) -> discord.Embed:
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

def check_ban_possible(guild: discord.Guild, member: discord.Member) -> str | None:
    bot_member = guild.me

    if member.id == guild.owner_id:
        return "❌ 서버 소유자는 차단할 수 없어요."
    if member.id == bot_member.id:
        return "❌ 저를 차단하시면 안 돼요!!"
    if not bot_member.guild_permissions.ban_members:
        return "❌ 봇 역할에 차단 권한이 없어요. 서버 설정 → 역할에서 권한을 확인해주세요."
    if member.top_role >= bot_member.top_role:
        return (
            f"❌ **역할 순서 권한 오류가 발생했어요.** {member.mention} 님의 최상위 역할이 "
            f"제 최상위 역할({bot_member.top_role.mention})보다 높거나 같아서 처리할 수 없어요."
        )
    return None

async def apply_ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str | None,
) -> tuple[bool, str]:
    try:
        await member.ban(reason=reason)
        return True, ""
    except discord.Forbidden as e:
        logger.error("Forbidden 발생 (member=%s): %s", member, e)
        logger.error(traceback.format_exc())
        return False, "❌ 봇에 차단 권한이 없어요."
    except discord.HTTPException as e:
        logger.error("HTTPException 발생 (member=%s): %s", member, e)
        logger.error(traceback.format_exc())
        return False, "❌ 차단 요청 중 오류가 발생했어요."
    except Exception as e:
        logger.error("알 수 없는 에러 (member=%s): %s: %s", member, type(e).__name__, e)
        logger.error(traceback.format_exc())
        return False, "❌ 알 수 없는 오류가 발생했어요."

@app_commands.command(name="차단", description="멤버를 서버에서 차단해요. (확인 버튼)")
@app_commands.describe(
    member="차단할 멤버를 선택해주세요.",
    reason="차단 사유. 기본값: 사유 없음",
)
async def ban_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "사유 없음",
):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ 이 명령어를 실행할 권한이 없어요", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("❌ 본인을 차단할 수 없어요.", ephemeral=True)
        return

    precheck_error = check_ban_possible(interaction.guild, member)
    if precheck_error:
        await interaction.response.send_message(precheck_error, ephemeral=True)
        return

    result = await run_confirmation_flow(
        interaction,
        confirm_title="차단 확인",
        confirm_description=f"{member.mention} 님을 서버에서 차단할까요?",
        confirm_color=discord.Color.red(),
        reason=reason,
        cancel_title="차단 요청 취소",
        cancel_description="차단 요청이 취소되었어요.",
        timeout_title="시간 초과",
        timeout_description="15초 내 선택이 없어 차단 요청이 취소되었어요.",
    )

    if result != "confirm":
        return

    success, error_message = await apply_ban(interaction, member, reason)

    if success:
        public_embed = build_embed(
            "차단 완료",
            f"{member.mention} 님을 서버에서 차단했어요.",
            discord.Color.green(),
            reason=reason,
            moderator=interaction.user,
        )
        await interaction.channel.send(embed=public_embed)
        await interaction.edit_original_response(content="✅ 차단이 수행되었어요.", embed=None, view=None)
    else:
        await interaction.edit_original_response(content=error_message, embed=None, view=None)