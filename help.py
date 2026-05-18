import discord
from discord import app_commands

@app_commands.command(name="도움", description="봇 명령어 도움말을 확인해요.")
@app_commands.describe(category="도움말 카테고리를 선택해 주세요.")
@app_commands.choices(
    category=[
        app_commands.Choice(name="일반", value="일반"),
        app_commands.Choice(name="음악", value="음악"),
        app_commands.Choice(name="관리", value="관리"),
        app_commands.Choice(name="정보", value="정보"),
        app_commands.Choice(name="주식", value="주식"),
    ]
)
async def help_slash(
    interaction: discord.Interaction,
    category: app_commands.Choice[str] = None
):
    if category is None:
        embed = discord.Embed(
            title="도움말",
            description="사용 가능한 명령어 카테고리예요.",
            color=discord.Color.blue()
        )
        embed.add_field(name="일반", value="일반 명령어 목록을 확인하려면 `/help 일반`을 입력하세요.", inline=False)
        embed.add_field(name="음악", value="음악 명령어 목록을 확인하려면 `/help 음악`을 입력하세요.", inline=False)
        embed.add_field(name="관리", value="관리 명령어 목록을 확인하려면 `/help 관리`를 입력하세요.", inline=False)
        embed.add_field(name="정보", value="정보 명령어 목록을 확인하려면 `/help 정보`를 입력하세요.", inline=False)
        embed.add_field(name="주식", value="주식 명령어 목록을 확인하려면 `/help 주식`를 입력하세요.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    cat = category.value
    if cat == "일반":
        embed = discord.Embed(title="일반 명령어", description="일반 명령어 목록이에요.", color=discord.Color.green())
        embed.add_field(name="draw <추첨인원 수> <추첨인원 1> ...", value="랜덤 추첨기를 실행해요. (항목별 띄어쓰기 필수)", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif cat == "음악":
        embed = discord.Embed(title="음악 명령어", description="음악 명령어 목록이에요.", color=discord.Color.orange())
        embed.add_field(name="join", value="봇을 음성 채널에 참여시켜요.", inline=False)
        embed.add_field(name="leave", value="봇을 음성 채널에서 나가게 해요.", inline=False)
        embed.add_field(name="play <URL>", value="지정한 URL의 음악을 재생해요.", inline=False)
        embed.add_field(name="skip", value="현재 재생 중인 곡을 스킵해요.", inline=False)
        embed.add_field(name="queue", value="현재 대기열을 확인해요.", inline=False)
        embed.add_field(name="stop", value="음악을 정지하고 대기열을 비워요.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif cat == "정보":
        embed = discord.Embed(title="정보 명령어", description="정보 명령어 목록이에요.", color=discord.Color.orange())
        embed.add_field(name="유저정보", value="유저 정보를 확인해요.", inline=False)
        embed.add_field(name="서버정보", value="서버의 정보를 확인해요.", inline=False)
        embed.add_field(name="봇정보", value="봇의 정보를 확인해요.", inline=False)
        embed.add_field(name="아바타", value="사용자의 아바타를 불러와요.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif cat == "관리":
        embed = discord.Embed(title="관리 명령어", description="관리 명령어 목록이에요.", color=discord.Color.red())
        embed.add_field(name="킥 <유저 멘션 / ID 입력> <사유>", value="해당 유저를 추방해요.", inline=False)
        embed.add_field(name="밴 <유저 멘션 / ID 입력> <사유>", value="해당 유저를 밴해요.", inline=False)
        embed.add_field(name="타임아웃 <유저 멘션 / ID 입력> <시간(분)> <사유>", value="사용자를 타임아웃해요.", inline=False)
        embed.add_field(name="pardon <유저 멘션 / ID 입력>", value="해당 유저의 타임아웃을 해제해요.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif cat == "주식":
        embed = discord.Embed(title="주식 명령어", description="주식 명령어 목록이에요.", color=discord.Color.red())
        embed.add_field(name="주식 <종목명> <간격>", value="해당 주식의 현재 주가를 확인해요.", inline=False)
        embed.add_field(name="관심종목", value="등록한 관심 종목을 확인해요.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("존재하지 않는 카테고리에요. `/help`로 사용 가능한 카테고리를 확인하세요.", ephemeral=True)