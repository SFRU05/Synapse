import discord
from discord.ext import commands
from discord import ui
from openai import OpenAI
import json
import os
from pathlib import Path
import asyncio
from dotenv import load_dotenv

load_dotenv()

# 개발자 ID 설정 (모든 서버에서 사용 가능)
DEVELOPER_IDS = [123456789, 987654321]  # 여기에 개발자 Discord ID 추가


class SettingsView(ui.View):
    """챗봇 설정 UI"""

    def __init__(self, cog, guild_id):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    @ui.button(label="💾 저장", style=discord.ButtonStyle.success)
    async def save_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        await interaction.followup.send("✅ 설정이 저장되었어요!", ephemeral=True)
        self.stop()

    @ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.stop()


class ChatBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.config_file = Path("server_config.json")
        self.load_config()
        self.bot_names = ["시냅아", "설탕아"]

        # 대화 히스토리 저장
        # key: (guild_id, channel_id, user_id, trigger_type)
        # value: [{"role":"user/assistant","content":"..."}]
        self.conversations = {}

    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {}
            self.save_config()

    def save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def is_enabled(self, guild_id):
        guild_id = str(guild_id)
        if guild_id not in self.config:
            self.config[guild_id] = {
                "enabled": True,
                "disabled_by_dev": False
            }
            self.save_config()
        return self.config[guild_id].get("enabled", True)

    def toggle(self, guild_id, status, disabled_by_dev=False):
        guild_id = str(guild_id)
        self.config[guild_id] = {
            "enabled": status,
            "disabled_by_dev": disabled_by_dev if not status else False
        }
        self.save_config()

    def is_developer(self, user_id):
        return user_id in DEVELOPER_IDS

    def is_disabled_by_dev(self, guild_id):
        guild_id = str(guild_id)
        if guild_id not in self.config:
            return False
        return self.config[guild_id].get("disabled_by_dev", False)

    def get_settings_embed(self, guild_id):
        """설정 현황 Embed 생성"""
        guild_id = str(guild_id)
        config = self.config.get(guild_id, {})

        embed = discord.Embed(
            title="⚙️ 챗봇 설정",
            description="아래 버튼으로 설정을 변경할 수 있어요!",
            color=discord.Color.blurple()
        )

        status = "✅ 활성화" if config.get("enabled", True) else "❌ 비활성화"
        dev_disabled = "🔒 YES" if config.get("disabled_by_dev", False) else "❌ NO"

        embed.add_field(name="🤖 챗봇 상태", value=status, inline=False)
        embed.add_field(name="🔐 개발자 비활성화", value=dev_disabled, inline=True)
        embed.set_footer(text="설정은 자동으로 저장됩니다.")

        return embed

    def _conv_key(self, message: discord.Message, trigger_type: str = None):
        """
        호출 방식에 따라 다른 히스토리 사용
        - trigger_type == "reply": 답장 (히스토리 이어감)
        - trigger_type == "mention" or "name": 새로 부름 (히스토리 초기화)
        """
        if trigger_type == "reply":
            return (message.guild.id, message.channel.id, message.author.id, "reply")
        else:
            return (message.guild.id, message.channel.id, message.author.id, "new")

    def _get_history(self, key):
        return self.conversations.setdefault(key, [])

    def _trim_history(self, history, max_turns=10):
        # user+assistant 한 쌍 = 1턴, 최대 10턴 유지
        max_messages = max_turns * 2
        if len(history) > max_messages:
            del history[: len(history) - max_messages]

    async def get_response_realtime(self, key, user_message, discord_message: discord.Message, guild_id):
        """실시간 스트리밍으로 Discord 메시지 업데이트"""
        try:
            history = self._get_history(key)

            system_content = (
                "너는 16살 한국 여자 캐릭터야. "
                "존댓말로 다정하게 대답해."
                "수학이나 과학 문제의 질문이나 문제 생성은 자세하고 구조적으로 해."
                "너를 만든 곳은 Project SignalCore야."
                "너의 이름은 Synapse야."
            )

            messages = [
                {
                    "role": "system",
                    "content": system_content,
                }
            ]

            # ✅ 최근 3개 메시지만 API에 보냄 (비용 절감)
            if len(history) > 3:
                messages.extend(history[-3:])
            else:
                messages.extend(history)

            messages.append({"role": "user", "content": user_message})

            stream = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-4o-mini",
                messages=messages,
                temperature=1,
                stream=True,
            )

            answer = ""
            last_update = 0

            # 스트림에서 토큰을 받으면서 Discord 메시지 업데이트
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    answer += chunk.choices[0].delta.content

                    # 0.5초마다 한번씩 업데이트 (Discord API 제한 고려)
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_update > 0.5:
                        try:
                            if len(answer) > 2000:
                                # 너무 길면 처음 2000자까지만 표시
                                await discord_message.edit(content=answer[:2000] + f"\n\n⏳ (계속 작성 중...)")
                            else:
                                await discord_message.edit(content=answer if answer else "⏳ 생각하고 있어요...")
                            last_update = current_time
                        except discord.HTTPException:
                            # API 제한에 걸렸을 때 처리
                            await asyncio.sleep(1)

            # 최종 응답 저장
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": answer})
            self._trim_history(history, max_turns=10)

            # 최종 메시지 업데이트
            if len(answer) > 2000:
                # 2000자 이상이면 여러 메시지로 분할
                chunks = [answer[i:i + 2000] for i in range(0, len(answer), 2000)]
                await discord_message.edit(content=chunks[0])
                for chunk in chunks[1:]:
                    await discord_message.reply(chunk, mention_author=False)
            else:
                await discord_message.edit(content=answer)

            return answer

        except Exception as e:
            error_msg = f"죄송해요. 오류가 발생했어요: {str(e)}"
            try:
                await discord_message.edit(content=error_msg)
            except:
                pass
            return error_msg

    async def _is_reply_to_bot(self, message: discord.Message) -> bool:
        if not message.reference:
            return False

        # resolved 사용 (캐시되어 있으면 빠름)
        resolved = message.reference.resolved
        if isinstance(resolved, discord.Message):
            return resolved.author.id == self.bot.user.id

        # 없으면 fetch 시도
        if message.reference.message_id:
            try:
                replied = await message.channel.fetch_message(message.reference.message_id)
                return replied.author.id == self.bot.user.id
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return False

        return False

    async def extract_message(self, message: discord.Message):
        # 1) 봇 메시지에 답장(Reply) 여부를 최우선 검사! (답장 방식 구분)
        if await self._is_reply_to_bot(message):
            content = message.content
            # 답장에 멘션 태그가 섞여 들어간 경우 제거
            for mention in message.mentions:
                content = (
                    content.replace(f"<@{mention.id}>", "")
                    .replace(f"<@!{mention.id}>", "")
                    .strip()
                )
            return (content if content else None), "reply"

        # 2) 멘션 호출 (새 대화 시작)
        if self.bot.user in message.mentions:
            content = message.content
            for mention in message.mentions:
                content = (
                    content.replace(f"<@{mention.id}>", "")
                    .replace(f"<@!{mention.id}>", "")
                    .strip()
                )
            return (content if content else None), "mention"

        # 3) 이름 호출 (새 대화 시작)
        for name in self.bot_names:
            if message.content.startswith(name):
                content = message.content[len(name):].strip()
                return (content if content else None), "name"

        return None, None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if not self.is_enabled(message.guild.id):
            return

        user_message, trigger_type = await self.extract_message(message)

        # 빈 호출 처리
        if user_message is None and trigger_type in ("mention", "name", "reply"):
            async with message.channel.typing():
                await message.reply("네? 부르셨어요?", mention_author=False)
            return

        # 정상 대화 처리
        if user_message is not None:
            async with message.channel.typing():
                key = self._conv_key(message, trigger_type)

                # 답장이 아니고 새로 부른 경우("mention", "name") 이전 히스토리 초기화
                if trigger_type != "reply":
                    self.conversations[key] = []

                # 실시간 스트리밍으로 응답 받기
                reply_message = await message.reply("⏳ 생각하고 있어요...", mention_author=False)
                await self.get_response_realtime(key, user_message, reply_message, message.guild.id)

    @commands.command()
    async def enable_ai(self, ctx):
        is_dev = self.is_developer(ctx.author.id)
        is_admin = ctx.author.guild_permissions.administrator
        is_dev_disabled = self.is_disabled_by_dev(ctx.guild.id)

        # 개발자가 비활성화한 경우: 개발자만 활성화 가능
        if is_dev_disabled and not is_dev:
            await ctx.send("❌ 개발자가 비활성화했습니다. 개발자만 활성화할 수 있어요!")
            return

        # 개발자 또는 어드민만 활성화 가능
        if not (is_dev or is_admin):
            await ctx.send("❌ 권한이 없습니다. 개발자 또는 관리자만 사용 가능해요!")
            return

        thinking = await ctx.send("생각하고 있어요..")
        self.toggle(ctx.guild.id, True, disabled_by_dev=False)
        await thinking.edit(content="✅ 챗봇을 활성화했어요!")

    @commands.command()
    async def disable_ai(self, ctx):
        is_dev = self.is_developer(ctx.author.id)
        is_admin = ctx.author.guild_permissions.administrator

        # 개발자 또는 어드민만 비활성화 가능
        if not (is_dev or is_admin):
            await ctx.send("❌ 권한이 없습니다. 개발자 또는 관리자만 사용 가능해요!")
            return

        thinking = await ctx.send("생각하고 있어요..")
        # 개발자가 비활성화하면 disabled_by_dev = True
        self.toggle(ctx.guild.id, False, disabled_by_dev=is_dev)

        if is_dev:
            await thinking.edit(content="❌ 챗봇을 비활성화했어요! (개발자 비활성화 - 개발자만 활성화 가능)")
        else:
            await thinking.edit(content="❌ 챗봇을 비활성화했어요!")

    @commands.command()
    async def ai_status(self, ctx):
        thinking = await ctx.send("생각하고 있어요..")

        if self.is_enabled(ctx.guild.id):
            status = "✅ 활성화"
        elif self.is_disabled_by_dev(ctx.guild.id):
            status = "❌ 비활성화 (개발자 비활성화 - 개발자만 활성화 가능)"
        else:
            status = "❌ 비활성화"

        await thinking.edit(content=f"현재 상태: {status}")

    @commands.command(name="설정")
    async def settings(self, ctx):
        """챗봇 설정 창 열기"""
        is_admin = ctx.author.guild_permissions.administrator
        is_dev = self.is_developer(ctx.author.id)

        if not (is_admin or is_dev):
            await ctx.send("❌ 권한이 없습니다. 관리자 또는 개발자만 사용 가능해요!")
            return

        embed = self.get_settings_embed(ctx.guild.id)
        view = SettingsView(self, ctx.guild.id)

        await ctx.send(embed=embed, view=view)

    @commands.command()
    async def reset_chat(self, ctx):
        # 현재 유저/채널의 대화 초기화 (모든 trigger_type)
        keys_to_remove = [
            (ctx.guild.id, ctx.channel.id, ctx.author.id, "reply"),
            (ctx.guild.id, ctx.channel.id, ctx.author.id, "new"),
        ]
        for key in keys_to_remove:
            self.conversations.pop(key, None)
        await ctx.send("🧹 이 채널에서 회원님의 대화 기억을 초기화했어요!")


async def setup(bot):
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise ValueError("❌ OPENAI_API_KEY가 .env에 없습니다!")

    await bot.add_cog(ChatBot(bot))