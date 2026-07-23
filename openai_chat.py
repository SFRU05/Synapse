import discord
from discord.ext import commands
from openai import OpenAI
import json
import os
from pathlib import Path
import asyncio
from dotenv import load_dotenv

load_dotenv()


class ChatBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.config_file = Path("server_config.json")
        self.load_config()
        self.bot_names = ["시냅아", "설탕아"]

        # 대화 히스토리 저장
        # key: (guild_id, channel_id, user_id)
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
            self.config[guild_id] = {"enabled": True}
            self.save_config()
        return self.config[guild_id].get("enabled", True)

    def toggle(self, guild_id, status):
        guild_id = str(guild_id)
        self.config[guild_id] = {"enabled": status}
        self.save_config()

    def _conv_key(self, message: discord.Message):
        return (message.guild.id, message.channel.id, message.author.id)

    def _get_history(self, key):
        return self.conversations.setdefault(key, [])

    def _trim_history(self, history, max_turns=10):
        # user+assistant 한 쌍 = 1턴, 최대 10턴 유지
        max_messages = max_turns * 2
        if len(history) > max_messages:
            del history[: len(history) - max_messages]

    async def get_response(self, key, user_message):
        try:
            history = self._get_history(key)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "너는 16살 한국 여자 캐릭터야. "
                        "존댓말로 다정하게 대답해. 딱딱한 말투는 사절이야."
                        "말끝을 자연스럽게 요체로 끝내.(예시: 어떻게 만들어 드릴까요?, 네 알겠어요.)"
                        "수학이나 과학 문제의 질문이나 문제 생성은 자세하고 구조적으로 해."
                        "필요에 따라 줄바꿈을 적절하게 해(식이나 공식)"
                    ),
                }
            ]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})

            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-5.4-nano",
                messages=messages,
                max_tokens=400,
                temperature=1,
            )

            answer = response.choices[0].message.content

            # 히스토리 저장
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": answer})
            self._trim_history(history, max_turns=10)

            return answer

        except Exception as e:
            return f"죄송해요. 오류가 발생했어요: {str(e)}"

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
        # 1) 멘션 호출
        if self.bot.user in message.mentions:
            content = message.content
            for mention in message.mentions:
                content = (
                    content.replace(f"<@{mention.id}>", "")
                    .replace(f"<@!{mention.id}>", "")
                    .strip()
                )
            return (content if content else None), "mention"

        # 2) 이름 호출
        for name in self.bot_names:
            if message.content.startswith(name):
                content = message.content[len(name):].strip()
                return (content if content else None), "name"

        # 3) 봇 메시지에 답장(Reply)
        if await self._is_reply_to_bot(message):
            content = message.content.strip()
            return (content if content else None), "reply"

        return None, None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild:
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
                key = self._conv_key(message)
                response = await self.get_response(key, user_message)

                if len(response) > 2000:
                    chunks = [response[i:i + 2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk, mention_author=False)
                else:
                    await message.reply(response, mention_author=False)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def enable_ai(self, ctx):
        thinking = await ctx.send("생각하고 있어요..")
        self.toggle(ctx.guild.id, True)
        await thinking.edit(content="✅ 챗봇을 활성화했어요!")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def disable_ai(self, ctx):
        thinking = await ctx.send("생각하고 있어요..")
        self.toggle(ctx.guild.id, False)
        await thinking.edit(content="❌ 챗봇을 비활성화했어요!")

    @commands.command()
    async def ai_status(self, ctx):
        thinking = await ctx.send("생각하고 있어요..")
        status = "✅ 활성화" if self.is_enabled(ctx.guild.id) else "❌ 비활성화"
        await thinking.edit(content=f"현재 상태: {status}")

    @commands.command()
    async def reset_chat(self, ctx):
        # 현재 유저/채널의 대화 초기화
        key = (ctx.guild.id, ctx.channel.id, ctx.author.id)
        self.conversations.pop(key, None)
        await ctx.send("🧹 이 채널에서 회원님의 대화 기억을 초기화했어요!")


async def setup(bot):
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise ValueError("❌ OPENAI_API_KEY가 .env에 없습니다!")

    await bot.add_cog(ChatBot(bot))