"""
유저가 봇 DM으로 메시지를 보내면
"이 내용으로 문의를 전송하시겠습니까?" 확인을 받고,
'전송' 버튼을 누르면 개발자에게 전달합니다.
15초 동안 응답이 없으면 자동으로 취소됩니다.

개발자에게 전달된 문의 메시지에는 "답변하기" 버튼이 달려있어서,
버튼을 누르면 입력창(모달)이 뜨고 거기에 입력한 내용이
문의를 보낸 유저에게 그대로 DM으로 전달됩니다.

⚠️ 주의: developer_commands.py 쪽에 이미 DM을 자동으로
   개발자에게 전달하는 리스너(forward_dm_to_developer)가 있다면,
   이 파일과 함께 쓰면 문의가 "확인 없이 자동 전달" + "확인 후 전달"
   두 번 일어날 수 있어요. 이 파일을 쓰실 거면 그쪽 리스너는
   지우거나 주석 처리하는 걸 추천드려요.
"""

import discord
from discord.ext import commands

# 개발자 ID 설정 (developer_commands.py의 DEVELOPER_IDS와 동일하게 맞춰주세요)
DEVELOPER_IDS = [725694061998243850]


# ----------------------------------------------------------------------
# 개발자가 문의자에게 답장을 보낼 때 쓰는 입력창(모달) + 버튼
# ----------------------------------------------------------------------
class ReplyModal(discord.ui.Modal, title="문의자에게 답장 보내기"):
    reply_input = discord.ui.TextInput(
        label="답장 내용",
        style=discord.TextStyle.paragraph,
        placeholder="문의자에게 보낼 답장을 입력하세요...",
        max_length=1500,
        required=True,
    )

    def __init__(self, bot: commands.Bot, target_user_id: int, target_user_name: str):
        super().__init__()
        self.bot = bot
        self.target_user_id = target_user_id
        self.target_user_name = target_user_name

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            target = await self.bot.fetch_user(self.target_user_id)
        except discord.NotFound:
            await interaction.followup.send("❌ 문의자를 찾을 수 없습니다. (계정이 삭제되었을 수 있어요)", ephemeral=True)
            return

        embed = discord.Embed(
            title="💬 문의 답장이 도착했습니다",
            description=self.reply_input.value,
            color=discord.Color.blurple()
        )
        embed.set_footer(text="문의 답장 · 추가로 궁금한 점이 있으면 다시 DM으로 남겨주세요")

        try:
            await target.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ **{target}**님에게 DM을 보낼 수 없습니다. (DM 차단 또는 봇과 서버 공유 안 됨)",
                ephemeral=True
            )
            return
        except discord.HTTPException as e:
            print(f"[dm_inquiry] 답장 전송 실패 (user_id={self.target_user_id}): {e!r}")
            await interaction.followup.send(f"❌ 전송 중 오류가 발생했습니다: `{e}`", ephemeral=True)
            return

        await interaction.followup.send(f"✅ **{target}**님에게 답장을 전송했습니다.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"[dm_inquiry] ReplyModal 오류: {error!r}")
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ 오류가 발생했습니다: `{error}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 오류가 발생했습니다: `{error}`", ephemeral=True)


class ReplyButtonView(discord.ui.View):
    """개발자에게 전달되는 문의 메시지에 붙는 '답변하기' 버튼"""

    def __init__(self, bot: commands.Bot, target_user_id: int, target_user_name: str):
        # 개발자가 나중에 언제든 답장할 수 있도록 타임아웃 없음
        super().__init__(timeout=None)
        self.bot = bot
        self.target_user_id = target_user_id
        self.target_user_name = target_user_name

    @discord.ui.button(label="답변하기", style=discord.ButtonStyle.blurple, emoji="↩️")
    async def reply_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ReplyModal(self.bot, self.target_user_id, self.target_user_name)
        )


# ----------------------------------------------------------------------
# 문의 전송 여부를 묻는 확인/취소 버튼 (15초 타임아웃)
# ----------------------------------------------------------------------
class InquiryConfirmView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.abc.User, content: str, attachments):
        super().__init__(timeout=15)  # 15초 동안 응답 없으면 on_timeout 호출
        self.bot = bot
        self.author = author
        self.content = content
        self.attachments = attachments
        self.message: discord.Message | None = None  # 타임아웃 시 수정할 원본 메시지

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ 본인만 확인할 수 있어요.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="전송", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        success_count = await self._forward_to_developers()
        if success_count > 0:
            content = "✅ 문의가 전송되었습니다. 답변을 기다려주세요!"
        else:
            content = (
                "⚠️ 문의 전송에 실패했어요. (개발자에게 DM을 보낼 수 없음)\n"
                "콘솔 로그에 자세한 에러가 출력되었을 거예요."
            )
        await interaction.response.edit_message(content=content, embed=None, view=None)
        self.stop()

    @discord.ui.button(label="취소", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="🚫 문의 전송이 취소되었습니다.",
            embed=None,
            view=None
        )
        self.stop()

    async def on_timeout(self):
        if self.message is not None:
            try:
                await self.message.edit(
                    content="⏰ 시간이 초과되어 문의 전송이 자동으로 취소되었습니다.",
                    embed=None,
                    view=None
                )
            except discord.HTTPException:
                pass

    async def _forward_to_developers(self) -> int:
        """개발자들에게 전달 시도. 성공한 개수를 반환."""
        embed = discord.Embed(
            title="📬 새로운 문의 도착",
            description=self.content or "*(텍스트 없음 - 첨부파일 등 확인)*",
            color=discord.Color.green(),
        )
        embed.set_author(name=str(self.author), icon_url=self.author.display_avatar.url)
        embed.add_field(name="보낸 사람 ID", value=str(self.author.id), inline=False)

        if self.attachments:
            embed.add_field(
                name="📎 첨부파일",
                value="\n".join(a.url for a in self.attachments),
                inline=False
            )

        success_count = 0
        for dev_id in DEVELOPER_IDS:
            try:
                dev = await self.bot.fetch_user(dev_id)
                await dev.send(
                    embed=embed,
                    view=ReplyButtonView(self.bot, self.author.id, str(self.author))
                )
                success_count += 1
            except discord.NotFound:
                print(f"[dm_inquiry] 개발자 ID를 찾을 수 없음: {dev_id} (DEVELOPER_IDS 설정 확인 필요)")
            except discord.Forbidden:
                print(f"[dm_inquiry] {dev_id}에게 DM 전송 권한 없음 (DM 차단 또는 봇과 서버 미공유)")
            except discord.HTTPException as e:
                print(f"[dm_inquiry] {dev_id}에게 전달 중 오류: {e!r}")

        return success_count


# ----------------------------------------------------------------------
# DM 수신 리스너
# ----------------------------------------------------------------------
class DMInquiry(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener(name="on_message")
    async def handle_dm(self, message: discord.Message):
        if message.author.bot:
            return

        if not isinstance(message.channel, discord.DMChannel):
            return

        preview_embed = discord.Embed(
            title="📨 문의 내용 확인",
            description=message.content or "*(텍스트 없음 - 첨부파일 등 확인)*",
            color=discord.Color.blurple()
        )
        if message.attachments:
            preview_embed.add_field(
                name="📎 첨부파일",
                value="\n".join(a.url for a in message.attachments),
                inline=False
            )

        view = InquiryConfirmView(self.bot, message.author, message.content, message.attachments)

        sent = await message.channel.send(
            content="아래 내용으로 문의를 전송하시겠습니까?\n(15초 이내 응답이 없으면 자동으로 취소됩니다)",
            embed=preview_embed,
            view=view
        )
        view.message = sent


# 💡 main.py에서 이 함수를 호출하여 Cog를 추가하게 됩니다.
async def setup(bot: commands.Bot):
    await bot.add_cog(DMInquiry(bot))