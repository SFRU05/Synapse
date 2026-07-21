import discord
from discord import app_commands
from discord.ext import commands
from openai import OpenAI

class SummarizeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = OpenAI()  # OPENAI_API_KEY는 환경변수에서 자동 로드

    @app_commands.command(name="대화요약", description="최근 대화를 요약합니다.")
    @app_commands.describe(count="요약할 최근 메시지 개수")
    @app_commands.choices(count=[
        app_commands.Choice(name="10개", value=10),
        app_commands.Choice(name="20개", value=20),
        app_commands.Choice(name="30개", value=30),
    ])
    async def summarize_chat(self, interaction: discord.Interaction, count: app_commands.Choice[int]):
        await interaction.response.defer(thinking=True, ephemeral=True)

        limit = count.value
        messages = []
        async for msg in interaction.channel.history(limit=limit):
            if msg.author.bot:
                continue
            content = msg.content.strip()
            if content:
                messages.append(f"{msg.author.display_name}: {content}")

        if not messages:
            await interaction.followup.send("요약할 메시지가 없어요.")
            return

        # history는 최신순으로 가져오므로 반전해서 오래된->최신 순으로 정렬
        messages.reverse()
        chat_text = "\n".join(messages)

        prompt = f"""
다음은 디스코드 대화입니다. 핵심만 한국어로 간결하게 요약해 주세요.
- 중요한 결정/요청/질문을 우선 정리
- 불필요한 반복은 제거
- 마지막에 한 줄 결론 추가
- 결론: (요약 내용) 했다는 대화가 오갔어요. 의 형식으로 자연스럽게 결론을 내려

대화:
{chat_text}
"""

        try:
            res = self.client.responses.create(
                model="gpt-5.4-nano",
                input=prompt
            )

            summary = res.output_text.strip()
            if not summary:
                summary = "요약 결과가 비어 있어요."

            # 디스코드 메시지 길이 제한 대응
            if len(summary) > 1900:
                summary = summary[:1900] + "\n...(생략)"

            await interaction.followup.send(f"📝 최근 {limit}개 대화 요약이에요:\n\n{summary}", ephemeral=True)


        except Exception as e:
            await interaction.followup.send(f"요약 중 오류가 발생했어요: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(SummarizeCog(bot))