import time
import discord
from discord import app_commands
from discord.ext import commands

# (유저 ID, 채널 ID) -> (선택한 메시지, 선택한 시각)
pending_selections: dict[tuple[int, int], tuple[discord.Message, float]] = {}

SELECTION_TIMEOUT = 60  # 초 단위 - 이 시간 안에 두 번째 메시지를 선택해야 함


class ConfirmClearView(discord.ui.View):
    def __init__(
        self,
        author_id: int,
        messages_to_delete: list[discord.Message],
        channel: discord.TextChannel
    ):
        super().__init__(timeout=20)  # 20초 후 자동 취소
        self.author_id = author_id
        self.messages_to_delete = messages_to_delete
        self.channel = channel
        self.confirmed = False
        self.message: discord.Message | None = None  # 확인창 메시지 객체 저장용

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ 이 명령어를 실행한 사람만 확인할 수 있어요.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="삭제 확인", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        await interaction.response.defer(ephemeral=False)

        try:
            await self.channel.delete_messages(self.messages_to_delete)
            result_text = (
                f"✅ 메시지 {len(self.messages_to_delete)}개를 삭제했어요.\n"
                f"👤 실행자: {interaction.user.mention}"
            )
        except discord.HTTPException:
            result_text = (
                f"❌ 14일 이상 지난 메시지가 포함되어 있어 삭제에 실패했어요.\n"
                f"👤 실행자: {interaction.user.mention}"
            )

        for child in self.children:
            child.disabled = True

        await interaction.edit_original_response(
            content=result_text,
            embed=None,
            view=self
        )
        self.stop()

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=f"삭제가 취소됐어요.",
            embed=None,
            view=self
        )
        self.stop()

    async def on_timeout(self):
        if self.confirmed:
            return

        for child in self.children:
            child.disabled = True

        # 20초 무응답 시 자동 취소 처리
        if self.message:
            try:
                await self.message.edit(
                    content="⏰ 20초 동안 응답이 없어 삭제가 자동으로 취소됐어요.",
                    embed=None,
                    view=self
                )
            except discord.HTTPException:
                pass

        self.stop()


class FirstSelectionView(discord.ui.View):
    def __init__(
        self,
        author_id: int,
        selected_message: discord.Message,
        channel: discord.TextChannel,
        key: tuple[int, int],
    ):
        super().__init__(timeout=SELECTION_TIMEOUT)
        self.author_id = author_id
        self.selected_message = selected_message
        self.channel = channel
        self.key = key

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ 이 선택을 시작한 사람만 사용할 수 있어요.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="이 메시지부터 아래까지 모두 청소",
        style=discord.ButtonStyle.danger,
        emoji="🧹"
    )
    async def clear_downward(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)

        # 선택한 메시지(포함)부터 최신 메시지까지 수집
        messages_to_delete = [self.selected_message]
        async for msg in self.channel.history(after=self.selected_message, oldest_first=True):
            messages_to_delete.append(msg)

        # 최대 100개 제한
        truncated = len(messages_to_delete) > 100
        messages_to_delete = messages_to_delete[:100]

        embed = discord.Embed(
            title="🗑️ 메시지 삭제 확인",
            description=(
                f"선택한 메시지부터 아래 방향으로 **{len(messages_to_delete)}개**를 삭제할까요?\n"
                + ("⚠️ 범위가 100개를 넘어 처음 100개만 삭제할 수 있어요.\n" if truncated else "")
                + "그래도 삭제할까요? 이 작업은 되돌릴 수 없어요."
            ),
            color=discord.Color.orange()
        )
        embed.add_field(
            name="기준 메시지",
            value=f"[바로가기]({self.selected_message.jump_url})",
            inline=False
        )

        # 기존 첫 선택 상태 제거(중복/혼선 방지)
        pending_selections.pop(self.key, None)

        confirm_view = ConfirmClearView(
            author_id=interaction.user.id,
            messages_to_delete=messages_to_delete,
            channel=self.channel
        )

        msg = await interaction.followup.send(embed=embed, view=confirm_view, ephemeral=False)
        confirm_view.message = msg  # timeout 시 메시지 수정용

        # 현재 버튼 비활성화
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)
        self.stop()

    async def on_timeout(self):
        # 타임아웃 시 버튼 비활성화 + pending 정리
        pending = pending_selections.get(self.key)
        if pending and pending[0].id == self.selected_message.id:
            pending_selections.pop(self.key, None)

        for child in self.children:
            child.disabled = True
        self.stop()


def setup_msg_clear(bot: commands.Bot):

    # ---------------- 슬래시 커맨드 ----------------
    @bot.tree.command(name="청소", description="최근 메시지를 지정한 개수만큼 삭제해요. (최대 100개)")
    @app_commands.describe(개수="삭제할 메시지 개수 (최대 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear_slash(interaction: discord.Interaction, 개수: app_commands.Range[int, 1, 100]):
        channel = interaction.channel

        # 1) 먼저 인터랙션 ACK (이거 없으면 "애플리케이션이 응답하지 않음")
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except discord.NotFound:
            # 이미 만료된 interaction
            return

        try:
            # 2) 삭제
            deleted = await channel.purge(limit=개수)

            # 3) 채널에 결과 메시지 출력 (원하는 포맷)
            await channel.send(
                f"✅ 메시지 {len(deleted)}개를 삭제했어요.\n"
                f"👤 실행자: {interaction.user.mention}"
            )

        except discord.Forbidden:
            await channel.send("❌ 메시지를 삭제할 권한이 없어요.")
        except discord.HTTPException:
            await channel.send("❌ 메시지 삭제 중 오류가 발생했어요.")
        finally:
            # 4) slash의 임시 응답(thinking) 제거
            try:
                await interaction.delete_original_response()
            except discord.HTTPException:
                pass

    # ---------------- 컨텍스트 메뉴 (범위 선택 방식) ----------------
    @bot.tree.context_menu(name="여기부터/여기까지 청소")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear_range(interaction: discord.Interaction, message: discord.Message):
        key = (interaction.user.id, interaction.channel.id)
        now = time.time()

        pending = pending_selections.get(key)

        # 이전 선택이 있고, 시간 초과되지 않았다면 -> 두 번째 선택으로 처리
        if pending and (now - pending[1]) <= SELECTION_TIMEOUT:
            first_message = pending[0]
            del pending_selections[key]

            # 같은 메시지를 두 번 선택한 경우
            if first_message.id == message.id:
                await interaction.response.send_message(
                    "❌ 같은 메시지를 두 번 선택했어요. 다시 시도해주세요.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=False)

            channel = interaction.channel

            # 시간순으로 앞선 메시지(earlier)와 뒤의 메시지(later) 구분
            if first_message.created_at <= message.created_at:
                earlier, later = first_message, message
            else:
                earlier, later = message, first_message

            # 두 메시지 사이(양 끝 포함) 메시지 수집
            messages_to_delete = [earlier]
            async for msg in channel.history(after=earlier, before=later, oldest_first=True):
                messages_to_delete.append(msg)
            messages_to_delete.append(later)

            # 최대 100개 제한
            truncated = len(messages_to_delete) > 100
            messages_to_delete = messages_to_delete[:100]

            embed = discord.Embed(
                title="🗑️ 메시지 삭제 확인",
                description=(
                    f"선택한 두 메시지 사이의 **{len(messages_to_delete)}개**의 메시지를 삭제할까요?\n\n"
                    + ("⚠️ 범위가 100개를 넘어 처음 100개만 삭제할 수 있어요.\n" if truncated else "")
                    + "그래도 삭제할까요? 이 작업은 되돌릴 수 없어요."
                ),
                color=discord.Color.orange()
            )
            embed.add_field(name="시작 메시지", value=f"[바로가기]({earlier.jump_url})", inline=True)
            embed.add_field(name="끝 메시지", value=f"[바로가기]({later.jump_url})", inline=True)

            view = ConfirmClearView(
                author_id=interaction.user.id,
                messages_to_delete=messages_to_delete,
                channel=channel
            )

            msg = await interaction.followup.send(embed=embed, view=view, ephemeral=False)
            view.message = msg  # timeout 시 메시지 수정용

        # 첫 번째 선택 -> 저장 + 버튼 안내
        else:
            pending_selections[key] = (message, now)

            view = FirstSelectionView(
                author_id=interaction.user.id,
                selected_message=message,
                channel=interaction.channel,
                key=key
            )

            await interaction.response.send_message(
                f"✅ 시작/끝 지점으로 [이 메시지]({message.jump_url})를 선택했어요.\n"
                f"이제 반대쪽 끝 메시지에도 같은 메뉴를 눌러주세요. "
                f"({SELECTION_TIMEOUT}초 안에 선택해야 해요.)\n\n"
                f"또는 아래 버튼으로 이 메시지부터 아래까지 바로 청소할 수 있어요.",
                ephemeral=True,
                view=view
            )

    # ---------------- 권한 에러 처리 ----------------
    @clear_slash.error
    async def clear_slash_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ 이 명령어를 사용하려면 메시지 관리 권한이 필요해요.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ 이 명령어를 사용하려면 메시지 관리 권한이 필요해요.",
                        ephemeral=True
                    )
            except discord.HTTPException:
                pass
            return

        raise error

    @clear_range.error
    async def clear_range_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ 이 명령어를 사용하려면 메시지 관리 권한이 필요해요.",
                ephemeral=True
            )
        else:
            raise error