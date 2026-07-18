import discord
from discord.ext import commands

DEVELOPER_IDS = [725694061998243850]


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
            await interaction.followup.send("❌ 문의자를 찾을 수 없습니다.", ephemeral=True)
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
            await interaction.followup.send(f"❌ **{target}**님에게 DM을 보낼 수 없습니다.", ephemeral=True)
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
    def __init__(self, bot: commands.Bot, target_user_id: int, target_user_name: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.target_user_id = target_user_id
        self.target_user_name = target_user_name

    @discord.ui.button(label="답변하기", style=discord.ButtonStyle.blurple, emoji="↩️")
    async def reply_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ReplyModal(self.bot, self.target_user_id, self.target_user_name)
        )


class InquiryConfirmView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.abc.User, topic: str, content: str, attachments):
        super().__init__(timeout=15)
        self.bot = bot
        self.author = author
        self.topic = topic
        self.content = content
        self.attachments = attachments
        self.message: discord.Message | None = None

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
                "콘솔 로그를 확인해주세요."
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
        embed = discord.Embed(
            title="📬 새로운 문의 도착",
            description=self.content or "*(텍스트 없음 - 첨부파일 등 확인)*",
            color=discord.Color.green(),
        )
        embed.set_author(name=str(self.author), icon_url=self.author.display_avatar.url)
        embed.add_field(name="🗂️ 문의 주제", value=self.topic, inline=False)
        embed.add_field(name="전송자 ID", value=str(self.author.id), inline=False)

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
                print(f"[dm_inquiry] 개발자 ID를 찾을 수 없음: {dev_id}")
            except discord.Forbidden:
                print(f"[dm_inquiry] {dev_id}에게 DM 전송 권한 없음")
            except discord.HTTPException as e:
                print(f"[dm_inquiry] {dev_id}에게 전달 중 오류: {e!r}")

        return success_count


# ✅ 새로 추가: 주제 선택 드롭다운 View
class InquiryTopicSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.abc.User, content: str, attachments):
        super().__init__(timeout=30)
        self.bot = bot
        self.author = author
        self.content = content
        self.attachments = attachments
        self.message: discord.Message | None = None

        self.topic_select = discord.ui.Select(
            placeholder="문의 종류를 선택하세요",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="버그제보", value="버그제보", emoji="🐞"),
                discord.SelectOption(label="건의", value="건의", emoji="💡"),
                discord.SelectOption(label="기타", value="기타", emoji="📝"),
            ]
        )
        self.topic_select.callback = self.on_topic_selected
        self.add_item(self.topic_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ 본인만 선택할 수 있어요.", ephemeral=True)
            return False
        return True

    async def on_topic_selected(self, interaction: discord.Interaction):
        topic = self.topic_select.values[0]

        preview_embed = discord.Embed(
            title="📨 문의 내용 확인",
            description=self.content or "*(텍스트 없음 - 첨부파일 등 확인)*",
            color=discord.Color.blurple()
        )
        preview_embed.add_field(name="🗂️ 선택한 주제", value=topic, inline=False)

        if self.attachments:
            preview_embed.add_field(
                name="📎 첨부파일",
                value="\n".join(a.url for a in self.attachments),
                inline=False
            )

        confirm_view = InquiryConfirmView(
            self.bot,
            self.author,
            topic,
            self.content,
            self.attachments
        )
        confirm_view.message = interaction.message

        await interaction.response.edit_message(
            content="문의 주제 선택이 완료되었습니다. **아래 내용으로 문의를 전송하시겠습니까?**\n(15초 이내 응답이 없으면 자동으로 취소됩니다)",
            embed=preview_embed,
            view=confirm_view
        )
        self.stop()

    async def on_timeout(self):
        if self.message is not None:
            try:
                await self.message.edit(
                    content="⏰ 시간이 초과되어 주제 선택이 자동으로 취소되었습니다.",
                    embed=None,
                    view=None
                )
            except discord.HTTPException:
                pass


class DMInquiry(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener(name="on_message")
    async def handle_dm(self, message: discord.Message):
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.DMChannel):
            return

        topic_view = InquiryTopicSelectView(
            self.bot,
            message.author,
            message.content,
            message.attachments
        )

        sent = await message.channel.send(
            content="문의 내용를 먼저 선택해주세요. (30초 이내)",
            view=topic_view
        )
        topic_view.message = sent


async def setup(bot: commands.Bot):
    await bot.add_cog(DMInquiry(bot))