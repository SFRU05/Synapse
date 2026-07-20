import discord
from discord import app_commands

async def apply_kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str | None,
) -> tuple[bool, str]:
    """실제 추방 적용. (성공 여부, 실패 시 사유 메시지) 반환."""
    try:
        await member.kick(reason=reason)
        return True, ""
    except discord.Forbidden as e:
        logger.error("Forbidden 발생 (member=%s): %s", member, e)
        logger.error(traceback.format_exc())
        return False, "❌ 봇에 추방 권한이 없어요."
    except discord.HTTPException as e:
        logger.error("HTTPException 발생 (member=%s): %s", member, e)
        logger.error(traceback.format_exc())
        return False, "❌ 추방 요청 중 오류가 발생했어요."
    except Exception as e:
        logger.error("알 수 없는 에러 (member=%s): %s: %s", member, type(e).__name__, e)
        logger.error(traceback.format_exc())
        return False, "❌ 알 수 없는 오류가 발생했어요."


def check_kick_possible(guild: discord.Guild, member: discord.Member) -> str | None:
    """추방용 사전 체크 (역할 계층/권한 문제를 API 호출 전에 확인)."""
    bot_member = guild.me

    if member.id == guild.owner_id:
        return "❌ 서버 소유자는 추방할 수 없어요."
    if member.id == bot_member.id:
        return "❌ 저를 추방하시면 안 돼요!!."
    if not bot_member.guild_permissions.kick_members:
        return "❌ 봇 역할에 추방 권한이 없어요. 서버 설정 → 역할에서 권한을 확인해주세요."
    if member.top_role >= bot_member.top_role:
        return (
            f"❌ **역할 순서 권한 오류가 발생했어요.** {member.mention} 님의 최상위 역할이 "
            f"제 최상위 역할({bot_member.top_role.mention})보다 높거나 같아서 처리할 수 없어요."
        )
    return None


@app_commands.command(name="추방", description="멤버를 추방해요. (확인 버튼)")
@app_commands.describe(
    member="추방할 멤버를 선택해주세요.",
    reason="추방 사유. 기본값: 사유 없음",
)
async def kick_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "사유 없음",
):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ 이 명령어를 실행할 권한이 없어요", ephemeral=True)
        return

    precheck_error = check_kick_possible(interaction.guild, member)
    if precheck_error:
        await interaction.response.send_message(precheck_error, ephemeral=True)
        return

    result = await run_confirmation_flow(
        interaction,
        confirm_title="추방 확인",
        confirm_description=f"{member.mention} 님을 서버에서 추방할까요?",
        confirm_color=discord.Color.red(),
        reason=reason,
        cancel_title="추방 요청 취소",
        cancel_description="추방 요청이 취소되었어요.",
        timeout_title="시간 초과",
        timeout_description="15초 내 선택이 없어 추방 요청이 취소되었어요.",
    )

    if result != "confirm":
        return

    success, error_message = await apply_kick(interaction, member, reason)

    if success:
        public_embed = build_embed(
            "추방 완료",
            f"{member.mention} 님이 추방되었어요.",
            discord.Color.green(),
            reason=reason,
            moderator=interaction.user,
        )
        await interaction.channel.send(embed=public_embed)
        await interaction.edit_original_response(content="✅ 추방이 수행되었어요.", embed=None, view=None)
    else:
        await interaction.edit_original_response(content=error_message, embed=None, view=None)