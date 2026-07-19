import discord
from discord.ext import commands
import sqlite3
from datetime import datetime, timezone

# 개발자 ID 설정
DEVELOPER_IDS = [725694061998243850]


def is_developer_check(ctx):
    return ctx.author.id in DEVELOPER_IDS


def chunk_text(items, limit=1000, sep=", "):
    """embed field 1024자 제한에 맞춰 문자열 리스트를 여러 조각으로 나눔"""
    chunks = []
    current = ""
    for item in items:
        add = (sep if current else "") + item
        if len(current) + len(add) > limit:
            chunks.append(current)
            current = item
        else:
            current += add
    if current:
        chunks.append(current)
    return chunks or ["없음"]


async def get_existing_invite(guild: discord.Guild):
    """
    서버에 이미 존재하는 초대 링크를 가져옵니다. (새로 생성하지 않음)
    - 초대 목록 조회에는 '서버 관리(Manage Server)' 권한이 필요합니다.
    반환값: discord.Invite 또는 None (초대가 없거나 권한 부족 시)
    """
    try:
        invites = await guild.invites()
    except discord.Forbidden:
        return None
    except discord.HTTPException:
        return None

    if not invites:
        return None

    # 만료되지 않고 사용 횟수 제한 없는 링크를 우선으로, 없으면 그냥 첫 번째 반환
    permanent = [i for i in invites if i.max_age == 0 and i.max_uses == 0]
    return permanent[0] if permanent else invites[0]


# 드롭다운 및 버튼 UI 클래스들 (이전 코드와 동일)
class GuildActionSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        options = []
        for guild in bot.guilds[:25]:
            options.append(
                discord.SelectOption(
                    label=guild.name,
                    description=f"ID: {guild.id} | 멤버 수: {guild.member_count}명",
                    value=str(guild.id)
                )
            )
        if not options:
            options.append(discord.SelectOption(label="참여 중인 서버 없음", value="none"))

        super().__init__(placeholder="⚙️ 관리할 서버를 선택해주세요...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message("❌ 개발자만 이 메뉴를 조작할 수 있어요.", ephemeral=True)
            return
        guild_id_str = self.values[0]
        if guild_id_str == "none":
            await interaction.response.send_message("❌ 선택할 수 있는 서버가 없어요.", ephemeral=True)
            return

        await interaction.response.send_message(
            content=f"선택된 서버 ID: `{guild_id_str}`\n수행할 작업을 선택해 주세요.",
            view=GuildActionButtons(interaction.client, int(guild_id_str)),
            ephemeral=True
        )


class OwnerMessageModal(discord.ui.Modal, title="서버 소유자에게 메시지 보내기"):
    message_input = discord.ui.TextInput(
        label="보낼 메시지 내용",
        style=discord.TextStyle.paragraph,
        placeholder="소유자에게 전달할 메시지를 입력하세요...",
        max_length=1500,
        required=True,
    )

    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        super().__init__()
        self.bot = bot
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = self.guild

        if guild.owner_id is None:
            await interaction.followup.send("❌ 이 서버의 소유자 정보를 확인할 수 없습니다.", ephemeral=True)
            return

        try:
            owner = await self.bot.fetch_user(guild.owner_id)
        except discord.NotFound:
            await interaction.followup.send("❌ 소유자 계정을 찾을 수 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📩 {guild.name} 서버 관련 안내",
            description=self.message_input.value,
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"보낸 사람: {interaction.user} (개발자)")

        try:
            await owner.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ **{owner}**님에게 DM을 보낼 수 없습니다. (DM 차단 또는 봇과 서버 공유 안 됨)",
                ephemeral=True
            )
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ 메시지 전송 중 오류가 발생했습니다: `{e}`", ephemeral=True)
            return

        await interaction.followup.send(
            f"✅ **{owner}** ({guild.name} 소유자)님에게 메시지를 전송했습니다.",
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ 오류가 발생했습니다: `{error}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ 오류가 발생했습니다: `{error}`", ephemeral=True)


class GuildActionButtons(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="서버 조회", style=discord.ButtonStyle.blurple, emoji="📊")
    async def view_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = self.bot.get_guild(self.guild_id)

            conn = sqlite3.connect("discord_logs.db")
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id FROM log_channels WHERE guild_id = ?", (self.guild_id,))
            log_channel = cursor.fetchone()
            cursor.execute("SELECT * FROM log_settings WHERE guild_id = ?", (self.guild_id,))
            log_settings = cursor.fetchone()
            conn.close()

            embed = discord.Embed(title="📊 서버 데이터 조회", description=f"서버 ID: `{self.guild_id}`",
                                  color=discord.Color.blurple())

            if guild:
                joined_at = guild.me.joined_at if guild.me else None
                joined_str = joined_at.strftime("%Y-%m-%d %H:%M UTC") if joined_at else "알 수 없음"

                embed.add_field(name="서버 이름", value=guild.name, inline=False)
                embed.add_field(name="소유자", value=f"{guild.owner} ({guild.owner_id})", inline=True)
                embed.add_field(name="멤버 수", value=f"{guild.member_count}명", inline=True)
                embed.add_field(name="서버 생성일", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
                embed.add_field(name="봇 초대 날짜", value=joined_str, inline=True)
            else:
                embed.add_field(name="⚠️ 안내", value="봇이 더 이상 이 서버에 없어 실시간 정보를 가져올 수 없습니다.", inline=False)

            embed.add_field(name="📋 로그 채널", value=f"채널 ID: `{log_channel[0]}`" if log_channel else "설정되지 않음",
                            inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: `{str(e)}`", ephemeral=True)

    @discord.ui.button(label="데이터 삭제", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            conn = sqlite3.connect("discord_logs.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM log_channels WHERE guild_id = ?", (self.guild_id,))
            cursor.execute("DELETE FROM log_settings WHERE guild_id = ?", (self.guild_id,))
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            await interaction.followup.send(f"✅ 데이터 삭제 완료 (삭제된 행: {deleted_count}개)", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: `{str(e)}`", ephemeral=True)

    @discord.ui.button(label="서버 나가기", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def leave_guild_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.followup.send("❌ 서버를 찾을 수 없어요.", ephemeral=True)
            return
        try:
            await guild.leave()
            await interaction.followup.send(f"✅ 서버에서 나갔어요.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: `{str(e)}`", ephemeral=True)

    @discord.ui.button(label="초대 링크", style=discord.ButtonStyle.green, emoji="🔗")
    async def get_invite_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.followup.send("❌ 서버를 찾을 수 없어요.", ephemeral=True)
            return
        try:
            invite = await get_existing_invite(guild)
            if invite is None:
                await interaction.followup.send(
                    f"❌ **{guild.name}**에 기존 초대 링크가 없거나, 조회할 권한(서버 관리)이 없어요.",
                    ephemeral=True
                )
                return
            await interaction.followup.send(f"🔗 **{guild.name}** 초대 링크: {invite.url}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: `{str(e)}`", ephemeral=True)

    @discord.ui.button(label="봇 권한", style=discord.ButtonStyle.gray, emoji="🔑")
    async def bot_permissions_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild = self.bot.get_guild(self.guild_id)
        if not guild or not guild.me:
            await interaction.followup.send("❌ 서버를 찾을 수 없어요.", ephemeral=True)
            return
        try:
            perms = guild.me.guild_permissions
            granted = [name.replace("_", " ") for name, value in perms if value]

            embed = discord.Embed(
                title=f"🔑 봇 권한 - {guild.name}",
                color=discord.Color.green() if perms.administrator else discord.Color.blurple()
            )
            if perms.administrator:
                embed.description = "⚠️ 이 서버에서 **관리자(Administrator)** 권한을 가지고 있어요."

            for i, part in enumerate(chunk_text(granted)):
                embed.add_field(
                    name=f"✅ 허용된 권한 ({len(granted)}개)" if i == 0 else "\u200b",
                    value=f"```{part}```",
                    inline=False
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 오류 발생: `{str(e)}`", ephemeral=True)

    @discord.ui.button(label="메시지 전송", style=discord.ButtonStyle.blurple, emoji="✉️")
    async def message_owner_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.response.send_message("❌ 서버를 찾을 수 없어요.", ephemeral=True)
            return
        # 모달은 defer 없이 바로 응답으로 보내야 합니다.
        await interaction.response.send_modal(OwnerMessageModal(self.bot, guild))


class GuildSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=60)
        self.add_item(GuildActionSelect(bot))

class DeveloperCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="개발")
    @commands.check(is_developer_check)
    async def developer_panel(self, ctx):
        embed = discord.Embed(
            title="🤖 개발자 전용 서버 제어판",
            description="하단의 드롭다운 메뉴에서 원하시는 서버를 관리해 주세요.",
            color=discord.Color.blurple()
        )
        total_users = sum(g.member_count for g in self.bot.guilds)
        embed.add_field(name="서버 수 / 총 유저 수", value=f"`{len(self.bot.guilds)}개` / `{total_users}명`", inline=True)
        embed.add_field(name="레이턴시", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)

        view = GuildSelectView(self.bot)
        await ctx.send(embed=embed, view=view)

    @developer_panel.error
    async def developer_panel_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 개발자만 사용 가능한 명령어에요.")

    # ------------------------------------------------------------------
    # 서버 목록 조회
    # ------------------------------------------------------------------
    @commands.command(name="서버목록", aliases=["servers"])
    @commands.check(is_developer_check)
    async def server_list(self, ctx):
        guilds = sorted(self.bot.guilds, key=lambda g: g.member_count or 0, reverse=True)

        if not guilds:
            await ctx.send("현재 참여 중인 서버가 없습니다.")
            return

        lines = [f"📋 **참여 중인 서버 ({len(guilds)}개)**\n"]
        for g in guilds:
            lines.append(f"`{g.id}` | **{g.name}** | 인원 {g.member_count}명")

        text = "\n".join(lines)
        for chunk in [text[i:i + 1900] for i in range(0, len(text), 1900)]:
            await ctx.send(chunk)

    # ------------------------------------------------------------------
    # 특정 서버 상세 정보 (인원수, 초대된 날짜 등)
    # ------------------------------------------------------------------
    @commands.command(name="서버정보", aliases=["serverinfo"])
    @commands.check(is_developer_check)
    async def server_info(self, ctx, guild_id: int = None):
        """예: -서버정보 123456789012345678 (안 넣으면 현재 서버 기준)"""
        guild = self.bot.get_guild(guild_id) if guild_id else ctx.guild

        if guild is None:
            await ctx.send("❌ 해당 ID의 서버를 찾을 수 없습니다. (봇이 참여 중이 아니거나 ID가 잘못됨)")
            return

        me = guild.me
        joined_at = me.joined_at if me else None
        joined_str = joined_at.strftime("%Y-%m-%d %H:%M UTC") if joined_at else "알 수 없음"

        embed = discord.Embed(title=f"🔎 서버 정보 - {guild.name}", color=discord.Color.blurple())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="서버 ID", value=str(guild.id), inline=False)
        embed.add_field(name="소유자", value=f"{guild.owner} ({guild.owner_id})", inline=False)
        embed.add_field(name="전체 인원", value=str(guild.member_count), inline=True)
        embed.add_field(name="서버 생성일", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="봇 초대 날짜", value=joined_str, inline=True)
        embed.add_field(name="부스트", value=f"Lv.{guild.premium_tier} ({guild.premium_subscription_count}부스트)", inline=True)

        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # 모든 서버의 봇 초대 날짜를 최근순으로 정렬해서 보기
    # ------------------------------------------------------------------
    @commands.command(name="초대날짜", aliases=["invitedates"])
    @commands.check(is_developer_check)
    async def invite_dates(self, ctx):
        data = []
        for g in self.bot.guilds:
            joined = g.me.joined_at if g.me else None
            data.append((g, joined))

        data.sort(key=lambda x: x[1] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        lines = ["📅 **서버별 초대 날짜 (최근순)**\n"]
        for g, joined in data:
            joined_str = joined.strftime("%Y-%m-%d %H:%M UTC") if joined else "알 수 없음"
            lines.append(f"`{g.id}` | **{g.name}** — {joined_str}")

        text = "\n".join(lines)
        for chunk in [text[i:i + 1900] for i in range(0, len(text), 1900)]:
            await ctx.send(chunk)

    # ------------------------------------------------------------------
    # 특정 유저가 함께 있는(공유하는) 서버 검색
    # ------------------------------------------------------------------
    @commands.command(name="유저서버검색", aliases=["findmutual"])
    @commands.check(is_developer_check)
    async def find_mutual_guilds(self, ctx, user_id: int):
        found = [g for g in self.bot.guilds if g.get_member(user_id)]

        if not found:
            await ctx.send(f"`{user_id}` 유저와 공유하는 서버가 없습니다.")
            return

        lines = [f"🔍 **`{user_id}`와 공유 중인 서버 ({len(found)}개)**\n"]
        for g in found:
            lines.append(f"`{g.id}` | **{g.name}**")

        await ctx.send("\n".join(lines))

    # ------------------------------------------------------------------
    # 서버 초대 링크 가져오기 (없으면 새로 생성)
    # ------------------------------------------------------------------
    @commands.command(name="초대코드", aliases=["invite", "getinvite"])
    @commands.check(is_developer_check)
    async def get_invite_code(self, ctx, guild_id: int = None):
        """예: -초대코드 123456789012345678 (안 넣으면 현재 서버 기준)"""
        guild = self.bot.get_guild(guild_id) if guild_id else ctx.guild

        if guild is None:
            await ctx.send("❌ 해당 ID의 서버를 찾을 수 없습니다.")
            return

        invite = await get_existing_invite(guild)
        if invite is None:
            await ctx.send(f"❌ **{guild.name}**에 기존 초대 링크가 없거나, 조회할 권한(서버 관리)이 없습니다.")
            return

        await ctx.send(f"🔗 **{guild.name}** 초대 링크: {invite.url}")

    # ------------------------------------------------------------------
    # 서버 내 봇의 권한 확인
    # ------------------------------------------------------------------
    @commands.command(name="봇권한", aliases=["botperms", "permissions"])
    @commands.check(is_developer_check)
    async def check_bot_permissions(self, ctx, guild_id: int = None):
        """예: -봇권한 123456789012345678 (안 넣으면 현재 서버 기준)"""
        guild = self.bot.get_guild(guild_id) if guild_id else ctx.guild

        if guild is None or guild.me is None:
            await ctx.send("❌ 해당 서버를 찾을 수 없거나 봇 정보가 없습니다.")
            return

        perms = guild.me.guild_permissions
        granted = [name.replace("_", " ") for name, value in perms if value]
        denied = [name.replace("_", " ") for name, value in perms if not value]

        embed = discord.Embed(
            title=f"🔑 봇 권한 - {guild.name}",
            color=discord.Color.green() if perms.administrator else discord.Color.blurple()
        )
        if perms.administrator:
            embed.description = "⚠️ 이 서버에서 **관리자(Administrator)** 권한을 가지고 있습니다."

        for i, part in enumerate(chunk_text(granted)):
            embed.add_field(
                name=f"✅ 허용된 권한 ({len(granted)}개)" if i == 0 else "\u200b",
                value=f"```{part}```",
                inline=False
            )
        if denied:
            for i, part in enumerate(chunk_text(denied)):
                embed.add_field(
                    name=f"❌ 없는 권한 ({len(denied)}개)" if i == 0 else "\u200b",
                    value=f"```{part}```",
                    inline=False
                )

        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # 서버 소유자에게 DM 보내기
    # ------------------------------------------------------------------
    @commands.command(name="주인에게메시지", aliases=["dmowner", "ownermessage"])
    @commands.check(is_developer_check)
    async def message_owner(self, ctx, guild_id: int, *, message: str):
        """예: -주인에게메시지 123456789012345678 안녕하세요, 문의드립니다."""
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await ctx.send("❌ 해당 ID의 서버를 찾을 수 없습니다.")
            return

        if guild.owner_id is None:
            await ctx.send("❌ 이 서버의 소유자 정보를 확인할 수 없습니다.")
            return

        try:
            owner = await self.bot.fetch_user(guild.owner_id)
        except discord.NotFound:
            await ctx.send("❌ 소유자 계정을 찾을 수 없습니다.")
            return

        embed = discord.Embed(
            title=f"📩 {guild.name} 서버 관련 안내",
            description=message,
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"보낸 사람: {ctx.author} (개발자)")

        try:
            await owner.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(f"❌ **{owner}**님에게 DM을 보낼 수 없습니다. (DM 차단 또는 봇과 서버 공유 안 됨)")
            return
        except discord.HTTPException as e:
            await ctx.send(f"❌ 메시지 전송 중 오류가 발생했습니다: `{e}`")
            return

        await ctx.send(f"✅ **{owner}** ({guild.name} 소유자)님에게 메시지를 전송했습니다.")

    # 새로 추가된 명령어들의 공통 에러 처리
    # (developer_panel은 자체 .error 핸들러가 있어 여기서 중복 처리되지 않습니다)
    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 개발자만 사용 가능한 명령어에요.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"❌ 필요한 값이 빠졌어요: `{error.param.name}`\n"
                f"사용법: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`"
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ 입력값이 올바르지 않아요: {error}")
        else:
            raise error

class CommandList(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="커맨드목록")
    async def list_commands(self, ctx: commands.Context):
        if ctx.author.id not in DEVELOPER_IDS:
            await ctx.send("이 명령어는 개발자만 사용할 수 있어요.")
            return
        commands_list = await self.bot.tree.fetch_commands()
        msg = "\n".join([f"`</{cmd.name}:{cmd.id}>`" for cmd in commands_list])
        await ctx.send(msg)

async def setup(bot: commands.Bot):
    await bot.add_cog(DeveloperCommands(bot))
    await bot.add_cog(CommandList(bot))