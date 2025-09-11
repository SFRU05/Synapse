import discord

async def send_help(ctx, category: str = None):
    if category is None:
        embed = discord.Embed(title="도움말", description="사용 가능한 명령어 카테고리입니다.", color=discord.Color.blue())
        embed.add_field(name="일반", value="일반 명령어 목록을 확인하려면 `-help 일반`을 입력하세요.", inline=False)
        embed.add_field(name="음악", value="음악 명령어 목록을 확인하려면 `-help 음악`을 입력하세요.", inline=False)
        embed.add_field(name="관리", value="관리 명령어 목록을 확인하려면 `-help 관리`를 입력하세요.", inline=False)
        embed.add_field(name="정보", value="정보 명령어 목록을 확인하려면 `-help 정보`를 입력하세요.", inline=False)
        await ctx.send(embed=embed)
    elif category == "일반":
        embed = discord.Embed(title="일반 명령어", description="일반 명령어 목록입니다.", color=discord.Color.green())
        embed.add_field(name="ping", value="봇의 응답 속도를 확인합니다.", inline=False)
        embed.add_field(name="draw <추첨인원 수> <추첨인원 1> <추첨인원 2>...", value="랜덤 추첨기를 실행합니다. (항목별 띄어쓰기 필수)", inline=False)
        embed.add_field(name="info", value="봇의 정보를 불러옵니다.", inline=False)
        await ctx.send(embed=embed)
    elif category == "음악":
        embed = discord.Embed(title="음악 명령어 (일시적 사용 불가)", description="음악 명령어 목록입니다.", color=discord.Color.orange())
        embed.add_field(name="join", value="봇을 음성 채널에 참여시킵니다.", inline=False)
        embed.add_field(name="leave", value="봇을 음성 채널에서 나가게 합니다.", inline=False)
        embed.add_field(name="play <URL>", value="지정한 URL의 음악을 재생합니다.", inline=False)
        embed.add_field(name="skip", value="현재 재생 중인 곡을 스킵합니다.", inline=False)
        embed.add_field(name="queue", value="현재 대기열을 확인합니다.", inline=False)
        embed.add_field(name="stop", value="음악을 정지하고 대기열을 비웁니다.", inline=False)
        await ctx.send(embed=embed)
    elif category == "정보":
        embed = discord.Embed(title="정보 명령어", description="정보 명령어 목록입니다.", color=discord.Color.orange())
        embed.add_field(name="userinfo", value="유저 정보를 확인합니다..", inline=False)
        embed.add_field(name="serverinfo", value="서버의 정보를 확인합니다.", inline=False)
        embed.add_field(name="info", value="봇의 정보를 확인합니다.", inline=False)
        embed.add_field(name="avatar", value="사용자의 아바타를 불러옵니다.", inline=False)
        await ctx.send(embed=embed)
    elif category == "관리":
        embed = discord.Embed(title="관리 명령어", description="관리 명령어 목록입니다.", color=discord.Color.red())
        embed.add_field(name="-kick <유저 멘션 / ID 입력> <사유>", value="해당 유저를 추방합니다.", inline=False)
        embed.add_field(name="-ban <개수>", value="지정한 개수만큼 메시지를 삭제합니다.", inline=False)
        embed.add_field(name="-timeout <유저 멘션 / ID 입력> <시간(분)> <사유>", value="입력한 시간만큼 사용자를 타임아웃합니다.", inline=False)
        embed.add_field(name="-pardon <유저 멘션 / ID 입력>", value="해당 유저의 타임아웃을 해제합니다.", inline=False)
        embed.add_field(name="-clear <개수>", value="지정한 개수만큼 메시지를 삭제합니다.", inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("존재하지 않는 카테고리입니다. `-help`로 사용 가능한 카테고리를 확인하세요.")