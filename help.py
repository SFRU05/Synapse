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
        embed.add_field(name="일반", value="일반 명령어 목록을 확인하려면 카테고리에서 `일반`을 선택해 주세요.", inline=False)
        embed.add_field(name="음악", value="음악 명령어 목록을 확인하려면 카테고리에서 `음악`을 선택해 주세요.", inline=False)
        embed.add_field(name="관리", value="관리 명령어 목록을 확인하려면 카테고리에서 `관리`를 선택해 주세요.", inline=False)
        embed.add_field(name="정보", value="정보 명령어 목록을 확인하려면 카테고리에서 `정보`를 선택해 주세요.", inline=False)
        embed.add_field(name="주식", value="주식 명령어 목록을 확인하려면 카테고리에서 `주식`을 선택해 주세요.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    cat = category.value
    if cat == "일반":
        embed = discord.Embed(title="일반 명령어", description="일반 명령어 목록이에요.", color=discord.Color.green())
        embed.add_field(name="추첨", value="랜덤 추첨기를 실행해요.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    elif cat == "음악":
        embed = discord.Embed(title="🎵 음악 명령어 도움말", description="음악 명령어 목록이에요. 원하는 기능을 찾아보세요.",
                              color=discord.Color.orange())

        # 1. 재생 관련 문단
        embed.add_field(name="✨ [ 재생 및 제어 ]", value="━" * 15, inline=False)
        embed.add_field(name="재생 시작", value="YouTube에서 곡을 검색하거나 URL로 재생해요.", inline=False)
        embed.add_field(name="재생 일시정지", value="재생을 일시정지해요.", inline=False)
        embed.add_field(name="재생 계속", value="일시정지된 재생을 계속해요.", inline=False)
        embed.add_field(name="재생 정지", value="재생을 멈추고 대기열을 초기화해요.", inline=False)
        embed.add_field(name="재생 이전", value="이전 곡으로 돌아갈게요.", inline=False)
        embed.add_field(name="재생 다음", value="다음 곡으로 넘어갈게요.", inline=False)
        embed.add_field(name="재생 반복", value="반복 모드를 설정할게요.", inline=False)
        embed.add_field(name="재생 자동재생", value="작곡가의 다른 음악을 자동재생할게요.", inline=False)
        embed.add_field(name="재생 지금", value="현재 재생 중인 곡 정보를 표시해요.", inline=False)
        embed.add_field(name="재생 나가", value="봇을 음성 채널에서 내보내요.", inline=False)

        # 2. 대기열 관련 문단
        embed.add_field(name="\u200b", value="━" * 15, inline=False)  # 구분을 위한 빈 공간 및 가로선
        embed.add_field(name="🎶 [ 대기열 관리 ]", value="━" * 15, inline=False)
        embed.add_field(name="대기열 확인", value="현재 대기열을 표시해요.", inline=False)
        embed.add_field(name="대기열 셔플", value="대기열을 무작위로 섞어요.", inline=False)
        embed.add_field(name="대기열 삭제", value="대기열에서 특정 곡을 삭제해요.", inline=False)
        embed.add_field(name="대기열 초기화", value="대기열을 전부 비워요.", inline=False)

        # 3. 볼륨 관련 문단
        embed.add_field(name="\u200b", value="━" * 15, inline=False)
        embed.add_field(name="🔊 [ 음량 설정 ]", value="━" * 15, inline=False)
        embed.add_field(name="볼륨 확인", value="현재 볼륨을 확인해요.", inline=False)
        embed.add_field(name="볼륨 설정", value="볼륨을 설정해요. (0-100)", inline=False)

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
        embed.add_field(name="추방", value="해당 유저를 추방해요.", inline=False)
        embed.add_field(name="차단", value="해당 유저를 차단해요.", inline=False)
        embed.add_field(name="타임아웃", value="사용자를 타임아웃(채팅 금지)해요.", inline=False)
        embed.add_field(name="pardon", value="해당 유저의 타임아웃을 해제해요.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    elif cat == "주식":
        embed = discord.Embed(title="주식 명령어", description="주식 명령어 목록이에요.", color=discord.Color.red())
        embed.add_field(name="주식", value="해당 주식의 현재 주가를 확인해요.", inline=False)
        embed.add_field(name="관심종목", value="등록한 관심 종목을 확인해요.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    else:
        await interaction.response.send_message("존재하지 않는 카테고리에요. `/도움` 명령어로 사용 가능한 카테고리를 확인해 주세요.", ephemeral=True)