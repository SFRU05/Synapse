import discord
from discord.ext import commands

import sqlite3
from datetime import datetime, timezone
DEVELOPER_IDS = [
    725694061998243850
]


def is_developer_check(ctx: commands.Context) -> bool:
    """개발자 여부를 확인합니다."""
    return ctx.author.id in DEVELOPER_IDS


def chunk_text(items, limit=1000, sep=", "):
    chunks = []
    current = ""

    for item in items:
        add_text = (sep if current else "") + item

        if len(current) + len(add_text) > limit:
            if current:
                chunks.append(current)

            current = item
        else:
            current += add_text

    if current:
        chunks.append(current)

    return chunks or ["없음"]


async def get_existing_invite(guild: discord.Guild):
    try:
        invites = await guild.invites()

    except discord.Forbidden:
        return None

    except discord.HTTPException:
        return None

    if not invites:
        return None

    # 만료되지 않고 사용 횟수 제한이 없는 초대를 우선 선택
    permanent_invites = [
        invite
        for invite in invites
        if invite.max_age == 0 and invite.max_uses == 0
    ]

    return (
        permanent_invites[0]
        if permanent_invites
        else invites[0]
    )


# =================================
# 서버 선택 드롭다운
# =================================

class GuildActionSelect(discord.ui.Select):
    def __init__(
        self,
        bot: commands.Bot,
        parent_view: "GuildSelectView"
    ):
        self.bot = bot
        self.parent_view = parent_view

        current_guilds = parent_view.get_current_guilds()
        options = []

        for guild in current_guilds:
            member_count = guild.member_count or 0

            options.append(
                discord.SelectOption(
                    label=guild.name[:100],
                    description=(
                        f"ID: {guild.id} | "
                        f"멤버 수: {member_count}명"
                    )[:100],
                    value=str(guild.id)
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="참여 중인 서버 없음",
                    description="현재 봇이 참여 중인 서버가 없습니다.",
                    value="none"
                )
            )

        current_page = parent_view.page + 1
        total_pages = parent_view.total_pages

        super().__init__(
            placeholder=(
                f"⚙️ 관리할 서버를 선택해주세요 "
                f"({current_page}/{total_pages})"
            ),
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                "❌ 개발자만 이 메뉴를 조작할 수 있어요.",
                ephemeral=True
            )
            return

        guild_id_text = self.values[0]

        if guild_id_text == "none":
            await interaction.response.send_message(
                "❌ 선택할 수 있는 서버가 없어요.",
                ephemeral=True
            )
            return

        guild_id = int(guild_id_text)

        await interaction.response.send_message(
            content=(
                f"선택된 서버 ID: `{guild_id}`\n"
                "수행할 작업을 선택해 주세요."
            ),
            view=GuildActionButtons(
                interaction.client,
                guild_id
            ),
            ephemeral=True
        )

class GuildSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=60)

        self.bot = bot

        # 멤버 수가 많은 서버부터 정렬
        self.guilds = sorted(
            bot.guilds,
            key=lambda guild: guild.member_count or 0,
            reverse=True
        )

        # Discord Select 메뉴의 옵션 최대 개수는 25개
        self.per_page = 25

        # 내부 페이지 번호는 0부터 시작
        self.page = 0

        self.total_pages = max(
            1,
            (len(self.guilds) + self.per_page - 1)
            // self.per_page
        )

        self.select_menu = GuildActionSelect(
            self.bot,
            self
        )

        self.add_item(self.select_menu)

        self.update_button_state()

    def get_current_guilds(self):
        start_index = self.page * self.per_page
        end_index = start_index + self.per_page

        return self.guilds[start_index:end_index]

    def update_button_state(self):
        current_page = self.page + 1
        page_text = f"{current_page}/{self.total_pages}"

        self.previous_button.label = (
            f"⬅️ 이전 ({page_text})"
        )

        self.next_button.label = (
            f"다음 ({page_text}) ➡️"
        )

        self.previous_button.disabled = (
            self.page <= 0
        )

        self.next_button.disabled = (
            self.page >= self.total_pages - 1
        )

    async def refresh_select_menu(self):
        self.remove_item(self.select_menu)

        self.select_menu = GuildActionSelect(
            self.bot,
            self
        )

        self.add_item(self.select_menu)

        self.update_button_state()

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                "❌ 개발자만 이 메뉴를 조작할 수 있어요.",
                ephemeral=True
            )
            return False

        return True

    @discord.ui.button(
        label="⬅️ 이전 (1/1)",
        style=discord.ButtonStyle.secondary,
        row=1
    )
    async def previous_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if self.page <= 0:
            await interaction.response.send_message(
                "❌ 첫 번째 페이지입니다.",
                ephemeral=True
            )
            return

        self.page -= 1

        await self.refresh_select_menu()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(
        label="다음 (1/1) ➡️",
        style=discord.ButtonStyle.secondary,
        row=1
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if self.page >= self.total_pages - 1:
            await interaction.response.send_message(
                "❌ 마지막 페이지입니다.",
                ephemeral=True
            )
            return

        self.page += 1

        await self.refresh_select_menu()
        await interaction.response.edit_message(view=self)

class OwnerMessageModal(
    discord.ui.Modal,
    title="서버 소유자에게 메시지 보내기"
):
    message_input = discord.ui.TextInput(
        label="보낼 메시지 내용",
        style=discord.TextStyle.paragraph,
        placeholder="소유자에게 전달할 메시지를 입력하세요...",
        max_length=1500,
        required=True
    )

    def __init__(
        self,
        bot: commands.Bot,
        guild: discord.Guild
    ):
        super().__init__()

        self.bot = bot
        self.guild = guild

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)

        guild = self.guild

        if guild.owner_id is None:
            await interaction.followup.send(
                "❌ 이 서버의 소유자 정보를 확인할 수 없습니다.",
                ephemeral=True
            )
            return

        try:
            owner = await self.bot.fetch_user(guild.owner_id)

        except discord.NotFound:
            await interaction.followup.send(
                "❌ 소유자 계정을 찾을 수 없습니다.",
                ephemeral=True
            )
            return

        except discord.HTTPException as error:
            await interaction.followup.send(
                f"❌ 소유자 정보를 가져오는 중 오류가 발생했습니다: `{error}`",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📩 {guild.name} 서버 관련 안내",
            description=self.message_input.value,
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text=f"보낸 사람: {interaction.user} (개발자)"
        )

        try:
            await owner.send(embed=embed)

        except discord.Forbidden:
            await interaction.followup.send(
                (
                    f"❌ **{owner}**님에게 DM을 보낼 수 없습니다.\n"
                    "DM 차단 또는 봇과 서버를 공유하지 않는 상태일 수 있습니다."
                ),
                ephemeral=True
            )
            return

        except discord.HTTPException as error:
            await interaction.followup.send(
                f"❌ 메시지 전송 중 오류가 발생했습니다: `{error}`",
                ephemeral=True
            )
            return

        await interaction.followup.send(
            (
                f"✅ **{owner}** "
                f"({guild.name} 소유자)님에게 메시지를 전송했습니다."
            ),
            ephemeral=True
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception
    ):
        if interaction.response.is_done():
            await interaction.followup.send(
                f"❌ 오류가 발생했습니다: `{error}`",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: `{error}`",
                ephemeral=True
            )

class GuildActionButtons(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        guild_id: int
    ):
        super().__init__(timeout=60)

        self.bot = bot
        self.guild_id = guild_id

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                "❌ 개발자만 이 메뉴를 조작할 수 있어요.",
                ephemeral=True
            )
            return False

        return True

    @discord.ui.button(
        label="서버 조회",
        style=discord.ButtonStyle.blurple,
        emoji="📊"
    )
    async def view_data(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            guild = self.bot.get_guild(self.guild_id)

            conn = sqlite3.connect("discord_logs.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT channel_id
                FROM log_channels
                WHERE guild_id = ?
                """,
                (self.guild_id,)
            )

            log_channel = cursor.fetchone()

            conn.close()

            embed = discord.Embed(
                title="📊 서버 데이터 조회",
                description=f"서버 ID: `{self.guild_id}`",
                color=discord.Color.blurple()
            )

            if guild:
                joined_at = (
                    guild.me.joined_at
                    if guild.me
                    else None
                )

                joined_text = (
                    joined_at.strftime("%Y-%m-%d %H:%M UTC")
                    if joined_at
                    else "알 수 없음"
                )

                owner_text = (
                    f"{guild.owner} ({guild.owner_id})"
                    if guild.owner
                    else f"알 수 없음 ({guild.owner_id})"
                )

                embed.add_field(
                    name="서버 이름",
                    value=guild.name,
                    inline=False
                )

                embed.add_field(
                    name="소유자",
                    value=owner_text,
                    inline=True
                )

                embed.add_field(
                    name="멤버 수",
                    value=f"{guild.member_count or 0}명",
                    inline=True
                )

                embed.add_field(
                    name="서버 생성일",
                    value=guild.created_at.strftime("%Y-%m-%d"),
                    inline=True
                )

                embed.add_field(
                    name="봇 초대 날짜",
                    value=joined_text,
                    inline=True
                )

            else:
                embed.add_field(
                    name="⚠️ 안내",
                    value=(
                        "봇이 더 이상 이 서버에 없어 "
                        "실시간 정보를 가져올 수 없습니다."
                    ),
                    inline=False
                )

            embed.add_field(
                name="📋 로그 채널",
                value=(
                    f"채널 ID: `{log_channel[0]}`"
                    if log_channel
                    else "설정되지 않음"
                ),
                inline=False
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True
            )

        except sqlite3.Error as error:
            await interaction.followup.send(
                f"❌ 데이터베이스 오류가 발생했습니다: `{error}`",
                ephemeral=True
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ 오류가 발생했습니다: `{error}`",
                ephemeral=True
            )

    @discord.ui.button(
        label="데이터 삭제",
        style=discord.ButtonStyle.danger,
        emoji="🗑️"
    )
    async def delete_data(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            conn = sqlite3.connect("discord_logs.db")
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM log_channels
                WHERE guild_id = ?
                """,
                (self.guild_id,)
            )

            deleted_channels = cursor.rowcount

            cursor.execute(
                """
                DELETE FROM log_settings
                WHERE guild_id = ?
                """,
                (self.guild_id,)
            )

            deleted_settings = cursor.rowcount

            conn.commit()
            conn.close()

            deleted_count = (
                deleted_channels + deleted_settings
            )

            await interaction.followup.send(
                f"✅ 데이터 삭제 완료 (삭제된 행: {deleted_count}개)",
                ephemeral=True
            )

        except sqlite3.Error as error:
            await interaction.followup.send(
                f"❌ 데이터베이스 오류가 발생했습니다: `{error}`",
                ephemeral=True
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ 오류가 발생했습니다: `{error}`",
                ephemeral=True
            )

    @discord.ui.button(
        label="서버 나가기",
        style=discord.ButtonStyle.secondary,
        emoji="🚪"
    )
    async def leave_guild_action(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        guild = self.bot.get_guild(self.guild_id)

        if guild is None:
            await interaction.followup.send(
                "❌ 서버를 찾을 수 없어요.",
                ephemeral=True
            )
            return

        try:
            await guild.leave()

            await interaction.followup.send(
                "✅ 서버에서 나갔어요.",
                ephemeral=True
            )

        except discord.HTTPException as error:
            await interaction.followup.send(
                f"❌ 서버에서 나가는 중 오류가 발생했습니다: `{error}`",
                ephemeral=True
            )

    @discord.ui.button(
        label="초대 링크",
        style=discord.ButtonStyle.green,
        emoji="🔗"
    )
    async def get_invite_action(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        guild = self.bot.get_guild(self.guild_id)

        if guild is None:
            await interaction.followup.send(
                "❌ 서버를 찾을 수 없어요.",
                ephemeral=True
            )
            return

        invite = await get_existing_invite(guild)

        if invite is None:
            await interaction.followup.send(
                (
                    f"❌ **{guild.name}**에 기존 초대 링크가 없거나, "
                    "초대 목록을 조회할 권한이 없습니다."
                ),
                ephemeral=True
            )
            return

        await interaction.followup.send(
            f"🔗 **{guild.name}** 초대 링크: {invite.url}",
            ephemeral=True
        )

    @discord.ui.button(
        label="봇 권한",
        style=discord.ButtonStyle.gray,
        emoji="🔑"
    )
    async def bot_permissions_action(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)

        guild = self.bot.get_guild(self.guild_id)

        if guild is None or guild.me is None:
            await interaction.followup.send(
                "❌ 서버를 찾을 수 없거나 봇 정보가 없습니다.",
                ephemeral=True
            )
            return

        try:
            permissions = guild.me.guild_permissions

            granted = [
                name.replace("_", " ")
                for name, value in permissions
                if value
            ]

            denied = [
                name.replace("_", " ")
                for name, value in permissions
                if not value
            ]

            embed = discord.Embed(
                title=f"🔑 봇 권한 - {guild.name}",
                color=(
                    discord.Color.green()
                    if permissions.administrator
                    else discord.Color.blurple()
                )
            )

            if permissions.administrator:
                embed.description = (
                    "⚠️ 이 서버에서 "
                    "**관리자(Administrator)** 권한을 가지고 있습니다."
                )

            for index, part in enumerate(chunk_text(granted)):
                embed.add_field(
                    name=(
                        f"✅ 허용된 권한 ({len(granted)}개)"
                        if index == 0
                        else "\u200b"
                    ),
                    value=f"```{part}```",
                    inline=False
                )

            if denied:
                for index, part in enumerate(chunk_text(denied)):
                    embed.add_field(
                        name=(
                            f"❌ 없는 권한 ({len(denied)}개)"
                            if index == 0
                            else "\u200b"
                        ),
                        value=f"```{part}```",
                        inline=False
                    )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ 오류가 발생했습니다: `{error}`",
                ephemeral=True
            )

    @discord.ui.button(
        label="메시지 전송",
        style=discord.ButtonStyle.blurple,
        emoji="✉️",
        row=1
    )
    async def message_owner_action(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        guild = self.bot.get_guild(self.guild_id)

        if guild is None:
            await interaction.response.send_message(
                "❌ 서버를 찾을 수 없어요.",
                ephemeral=True
            )
            return

        # 모달은 defer 없이 바로 응답해야 합니다.
        await interaction.response.send_modal(
            OwnerMessageModal(self.bot, guild)
        )

class DeveloperCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="개발")
    @commands.check(is_developer_check)
    async def developer_panel(
        self,
        ctx: commands.Context
    ):
        embed = discord.Embed(
            title="🤖 개발자 전용 서버 제어판",
            description=(
                "하단의 드롭다운에서 관리할 서버를 선택해 주세요."
            ),
            color=discord.Color.blurple()
        )

        total_users = sum(
            guild.member_count or 0
            for guild in self.bot.guilds
        )

        embed.add_field(
            name="서버 수 / 총 유저 수",
            value=(
                f"`{len(self.bot.guilds)}개` / "
                f"`{total_users}명`"
            ),
            inline=True
        )

        embed.add_field(
            name="레이턴시",
            value=f"`{round(self.bot.latency * 1000)}ms`",
            inline=True
        )

        await ctx.send(
            embed=embed,
            view=GuildSelectView(self.bot)
        )

    @developer_panel.error
    async def developer_panel_error(
        self,
        ctx: commands.Context,
        error
    ):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(
                "❌ 개발자만 사용 가능한 명령어에요."
            )

    @commands.command(
        name="서버목록",
        aliases=["servers"]
    )
    @commands.check(is_developer_check)
    async def server_list(
        self,
        ctx: commands.Context
    ):
        guilds = sorted(
            self.bot.guilds,
            key=lambda guild: guild.member_count or 0,
            reverse=True
        )

        if not guilds:
            await ctx.send(
                "현재 참여 중인 서버가 없습니다."
            )
            return

        lines = [
            f"📋 **참여 중인 서버 ({len(guilds)}개)**\n"
        ]

        for guild in guilds:
            lines.append(
                f"`{guild.id}` | "
                f"**{guild.name}** | "
                f"인원 {guild.member_count or 0}명"
            )

        text = "\n".join(lines)

        for index in range(0, len(text), 1900):
            await ctx.send(text[index:index + 1900])

    @commands.command(
        name="서버정보",
        aliases=["serverinfo"]
    )
    @commands.check(is_developer_check)
    async def server_info(
        self,
        ctx: commands.Context,
        guild_id: int = None
    ):

        guild = (
            self.bot.get_guild(guild_id)
            if guild_id
            else ctx.guild
        )

        if guild is None:
            await ctx.send(
                "❌ 해당 ID의 서버를 찾을 수 없습니다."
            )
            return

        me = guild.me
        joined_at = me.joined_at if me else None

        joined_text = (
            joined_at.strftime("%Y-%m-%d %H:%M UTC")
            if joined_at
            else "알 수 없음"
        )

        owner_text = (
            f"{guild.owner} ({guild.owner_id})"
            if guild.owner
            else f"알 수 없음 ({guild.owner_id})"
        )

        embed = discord.Embed(
            title=f"🔎 서버 정보 - {guild.name}",
            color=discord.Color.blurple()
        )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.add_field(
            name="서버 ID",
            value=str(guild.id),
            inline=False
        )

        embed.add_field(
            name="소유자",
            value=owner_text,
            inline=False
        )

        embed.add_field(
            name="전체 인원",
            value=str(guild.member_count or 0),
            inline=True
        )

        embed.add_field(
            name="서버 생성일",
            value=guild.created_at.strftime("%Y-%m-%d"),
            inline=True
        )

        embed.add_field(
            name="봇 초대 날짜",
            value=joined_text,
            inline=True
        )

        embed.add_field(
            name="부스트",
            value=(
                f"Lv.{guild.premium_tier} "
                f"({guild.premium_subscription_count or 0}부스트)"
            ),
            inline=True
        )

        await ctx.send(embed=embed)

    @commands.command(
        name="초대날짜",
        aliases=["invitedates"]
    )
    @commands.check(is_developer_check)
    async def invite_dates(
        self,
        ctx: commands.Context
    ):
        data = []

        for guild in self.bot.guilds:
            joined_at = (
                guild.me.joined_at
                if guild.me
                else None
            )

            data.append((guild, joined_at))

        data.sort(
            key=lambda item: (
                item[1]
                or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True
        )

        lines = [
            "📅 **서버별 초대 날짜 (최근순)**\n"
        ]

        for guild, joined_at in data:
            joined_text = (
                joined_at.strftime("%Y-%m-%d %H:%M UTC")
                if joined_at
                else "알 수 없음"
            )

            lines.append(
                f"`{guild.id}` | "
                f"**{guild.name}** — {joined_text}"
            )

        text = "\n".join(lines)

        for index in range(0, len(text), 1900):
            await ctx.send(text[index:index + 1900])

    @commands.command(
        name="유저서버검색",
        aliases=["findmutual"]
    )
    @commands.check(is_developer_check)
    async def find_mutual_guilds(
        self,
        ctx: commands.Context,
        user_id: int
    ):
        found_guilds = [
            guild
            for guild in self.bot.guilds
            if guild.get_member(user_id)
        ]

        if not found_guilds:
            await ctx.send(
                f"`{user_id}` 유저와 공유하는 서버가 없습니다."
            )
            return

        lines = [
            (
                f"🔍 **`{user_id}`와 공유 중인 서버 "
                f"({len(found_guilds)}개)**\n"
            )
        ]

        for guild in found_guilds:
            lines.append(
                f"`{guild.id}` | **{guild.name}**"
            )

        text = "\n".join(lines)

        for index in range(0, len(text), 1900):
            await ctx.send(text[index:index + 1900])

    @commands.command(
        name="초대코드",
        aliases=["invite", "getinvite"]
    )
    @commands.check(is_developer_check)
    async def get_invite_code(
        self,
        ctx: commands.Context,
        guild_id: int = None
    ):
        """
        사용법:
        -초대코드
        -초대코드 서버ID
        """
        guild = (
            self.bot.get_guild(guild_id)
            if guild_id
            else ctx.guild
        )

        if guild is None:
            await ctx.send(
                "❌ 해당 ID의 서버를 찾을 수 없습니다."
            )
            return

        invite = await get_existing_invite(guild)

        if invite is None:
            await ctx.send(
                (
                    f"❌ **{guild.name}**에 기존 초대 링크가 없거나, "
                    "조회할 권한이 없습니다."
                )
            )
            return

        await ctx.send(
            f"🔗 **{guild.name}** 초대 링크: {invite.url}"
        )

    @commands.command(
        name="봇권한",
        aliases=["botperms", "permissions"]
    )
    @commands.check(is_developer_check)
    async def check_bot_permissions(
        self,
        ctx: commands.Context,
        guild_id: int = None
    ):
        guild = (
            self.bot.get_guild(guild_id)
            if guild_id
            else ctx.guild
        )

        if guild is None or guild.me is None:
            await ctx.send(
                "❌ 해당 서버를 찾을 수 없거나 "
                "봇 정보가 없습니다."
            )
            return

        permissions = guild.me.guild_permissions

        granted = [
            name.replace("_", " ")
            for name, value in permissions
            if value
        ]

        denied = [
            name.replace("_", " ")
            for name, value in permissions
            if not value
        ]

        embed = discord.Embed(
            title=f"🔑 봇 권한 - {guild.name}",
            color=(
                discord.Color.green()
                if permissions.administrator
                else discord.Color.blurple()
            )
        )

        if permissions.administrator:
            embed.description = (
                "⚠️ 이 서버에서 "
                "**관리자(Administrator)** 권한을 가지고 있습니다."
            )

        for index, part in enumerate(chunk_text(granted)):
            embed.add_field(
                name=(
                    f"✅ 허용된 권한 ({len(granted)}개)"
                    if index == 0
                    else "\u200b"
                ),
                value=f"```{part}```",
                inline=False
            )

        if denied:
            for index, part in enumerate(chunk_text(denied)):
                embed.add_field(
                    name=(
                        f"❌ 없는 권한 ({len(denied)}개)"
                        if index == 0
                        else "\u200b"
                    ),
                    value=f"```{part}```",
                    inline=False
                )

        await ctx.send(embed=embed)

    @commands.command(
        name="주인에게메시지",
        aliases=["dmowner", "ownermessage"]
    )
    @commands.check(is_developer_check)
    async def message_owner(
        self,
        ctx: commands.Context,
        guild_id: int,
        *,
        message: str
    ):
        guild = self.bot.get_guild(guild_id)

        if guild is None:
            await ctx.send(
                "❌ 해당 ID의 서버를 찾을 수 없습니다."
            )
            return

        if guild.owner_id is None:
            await ctx.send(
                "❌ 이 서버의 소유자 정보를 확인할 수 없습니다."
            )
            return

        try:
            owner = await self.bot.fetch_user(guild.owner_id)

        except discord.NotFound:
            await ctx.send(
                "❌ 소유자 계정을 찾을 수 없습니다."
            )
            return

        except discord.HTTPException as error:
            await ctx.send(
                f"❌ 소유자 정보를 가져오는 중 오류가 발생했습니다: `{error}`"
            )
            return

        embed = discord.Embed(
            title=f"📩 {guild.name} 서버 관련 안내",
            description=message,
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text=f"보낸 사람: {ctx.author} (개발자)"
        )

        try:
            await owner.send(embed=embed)

        except discord.Forbidden:
            await ctx.send(
                (
                    f"❌ **{owner}**님에게 DM을 보낼 수 없습니다. "
                    "(DM 차단 또는 봇과 서버를 공유하지 않음)"
                )
            )
            return

        except discord.HTTPException as error:
            await ctx.send(
                f"❌ 메시지 전송 중 오류가 발생했습니다: `{error}`"
            )
            return

        await ctx.send(
            (
                f"✅ **{owner}** "
                f"({guild.name} 소유자)님에게 메시지를 전송했습니다."
            )
        )

    async def cog_command_error(
        self,
        ctx: commands.Context,
        error
    ):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(
                "❌ 개발자만 사용 가능한 명령어에요."
            )

        elif isinstance(
            error,
            commands.MissingRequiredArgument
        ):
            await ctx.send(
                f"❌ 필요한 값이 빠졌어요: `{error.param.name}`\n"
                f"사용법: "
                f"`{ctx.prefix}{ctx.command.qualified_name} "
                f"{ctx.command.signature}`"
            )

        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                f"❌ 입력값이 올바르지 않아요: {error}"
            )

        else:
            raise error


# ============================================================
# 커맨드 목록 Cog
# ============================================================

class CommandList(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="커맨드목록")
    async def list_commands(
        self,
        ctx: commands.Context
    ):
        if ctx.author.id not in DEVELOPER_IDS:
            await ctx.send(
                "이 명령어는 개발자만 사용할 수 있어요."
            )
            return

        try:
            commands_list = await self.bot.tree.fetch_commands()

        except discord.HTTPException as error:
            await ctx.send(
                f"❌ 슬래시 커맨드 목록을 가져올 수 없습니다: `{error}`"
            )
            return

        if not commands_list:
            await ctx.send(
                "등록된 슬래시 커맨드가 없습니다."
            )
            return

        message = "\n".join(
            f"`</{command.name}:{command.id}>`"
            for command in commands_list
        )

        for index in range(0, len(message), 1900):
            await ctx.send(message[index:index + 1900])

async def setup(bot: commands.Bot):
    await bot.add_cog(
        DeveloperCommands(bot)
    )

    await bot.add_cog(
        CommandList(bot)
    )