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
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.config_file = Path("server_config.json")
        self.load_config()
        self.bot_names = ["시냅아", "설탕아"]

    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {}
            self.save_config()

    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
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

    async def get_response(self, user_message):
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "너는 16살 한국 여자 캐릭터야. 존댓말로 다정하게 대답해. 말끝을 '-요!', '-요.', '-어요!', '-어요.'로 마무리해. 답변은 항상 자세하고 구조적으로 해줘."
                    },
                    {"role": "user", "content": user_message}
                ],
                max_tokens=400,
                temperature=1
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"죄송해요. 오류가 발생했어요: {str(e)}"

    def extract_message(self, message):
        if self.bot.user in message.mentions:
            content = message.content
            for mention in message.mentions:
                content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "").strip()
            return content if content else None, True

        for name in self.bot_names:
            if message.content.startswith(name):
                content = message.content[len(name):].strip()
                return content if content else None, False

        return None, False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if not message.guild:
            return

        if not self.is_enabled(message.guild.id):
            return

        user_message, is_mention = self.extract_message(message)

        if user_message is None and (is_mention or any(message.content.startswith(name) for name in self.bot_names)):
            async with message.channel.typing():
                await message.reply("네? 부르셨어요?", mention_author=False)
            return

        if user_message is not None:
            async with message.channel.typing():
                response = await self.get_response(user_message)

                if len(response) > 2000:
                    chunks = [response[i:i + 2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk, mention_author=False)
                else:
                    await message.reply(response, mention_author=False)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def enable_ai(self, ctx):
        self.toggle(ctx.guild.id, True)
        await ctx.send("✅ 챗봇을 활성화했어요!")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def disable_ai(self, ctx):
        self.toggle(ctx.guild.id, False)
        await ctx.send("❌ 챗봇을 비활성화했어요!")

    @commands.command()
    async def ai_status(self, ctx):
        status = "✅ 활성화" if self.is_enabled(ctx.guild.id) else "❌ 비활성화"
        await ctx.send(f"현재 상태: {status}")


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="stop")
    @commands.is_owner()
    async def shutdown(self, ctx):
        await ctx.send("👋 봇을 종료합니다!")
        await self.bot.close()

    @commands.command(name="check")
    async def check_bot(self, ctx):
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 응답: {latency}ms")


async def setup(bot):
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        raise ValueError("❌ OPENAI_API_KEY가 .env에 없습니다!")

    await bot.add_cog(ChatBot(bot))
    await bot.add_cog(AdminCog(bot))