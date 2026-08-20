"""
주차별(7일 단위) 멤버 채팅량 집계 기능
----------------------------------------
사용법 (봇에 이 cog을 로드한 뒤):

    !주간통계                      -> 이번달 1일부터 지금까지, 주차별로 전체 집계
    !주간통계 이번주                -> 이번달 1일 기준으로 나눈 주차 중, "이번주"에 해당하는 구간만 집계
    !주간통계 이번달 #일반 #공지     -> 이번달 전체를 지정 채널에서만 집계

- 첫 인자(범위): "이번주" 또는 "이번달" (생략 시 "이번달")
- 이후 인자: 집계할 채널 멘션 (생략하면 봇이 읽을 수 있는 모든 텍스트 채널을 집계합니다.)

주차 기준:
- 항상 "이번달 1일"을 1주차의 시작으로 고정합니다. (1~7일=1주차, 8~14일=2주차, ...)
- "이번주" 범위를 선택하면 오늘이 속한 주차 구간만 잘라서 보여줍니다.

주의:
- message_content Intent가 반드시 활성화되어 있어야 합니다.
- 채널 히스토리를 전부 훑기 때문에 서버가 크거나 기간이 길면 시간이 꽤 걸립니다.
- discord.py 는 v2.x 기준으로 작성했습니다.
"""

import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from collections import defaultdict


class WeeklyStats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="주간통계")
    @commands.has_permissions(manage_guild=True)  # 아무나 못 돌리게 권한 제한 (필요 없으면 삭제)
    async def weekly_stats(
        self,
        ctx: commands.Context,
        scope: str = "이번달",
        *channels: discord.TextChannel,
    ):
        scope = scope.strip()
        if scope not in ("이번주", "이번달"):
            await ctx.send('범위는 "이번주" 또는 "이번달"만 지정할 수 있어요. 예: `!주간통계 이번주`')
            return

        now = datetime.now(timezone.utc)

        # 1. 이번달 1일 = 항상 1주차 시작 기준점
        month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        def week_index(dt: datetime) -> int:
            delta_days = (dt - month_start).days
            return delta_days // 7 + 1  # 1주차부터 시작

        this_week = week_index(now)

        # 2. 범위에 따라 실제로 조회할 구간(start~end) 결정
        if scope == "이번달":
            start = month_start
            end = now
        else:  # 이번주
            start = month_start + timedelta(days=(this_week - 1) * 7)
            end = min(start + timedelta(days=7), now + timedelta(seconds=1))

        # 3. 집계 대상 채널 결정
        target_channels = list(channels) if channels else [
            ch for ch in ctx.guild.text_channels
            if ch.permissions_for(ctx.guild.me).read_message_history
        ]

        await ctx.send(
            f"집계를 시작합니다. (범위: {scope} / {start.date()} ~ {end.date()} "
            f"/ 채널 수: {len(target_channels)}개)\n"
            f"메시지 양에 따라 시간이 오래 걸릴 수 있어요..."
        )

        total_weeks = week_index(end - timedelta(seconds=1)) if scope == "이번달" else this_week
        start_for_history = start

        # stats[week][member_id][channel_id] = count
        stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        member_names = {}  # id -> 표시 이름 캐시
        channel_names = {}  # id -> 채널 이름 캐시

        # 4. 채널별로 히스토리 순회
        for channel in target_channels:
            channel_names[channel.id] = channel.name
            try:
                async for message in channel.history(
                    after=start_for_history, before=end, limit=None, oldest_first=True
                ):
                    if message.author.bot:
                        continue
                    wk = week_index(message.created_at)
                    if wk < 1:
                        continue
                    stats[wk][message.author.id][channel.id] += 1
                    if message.author.id not in member_names:
                        member_names[message.author.id] = (
                            message.author.display_name
                        )
            except discord.Forbidden:
                continue  # 권한 없는 채널은 스킵
            except discord.HTTPException:
                continue

        # 5. txt 파일로 정리
        lines = []
        lines.append(f"채팅량 집계 [{scope}] ({start.date()} ~ {(end - timedelta(seconds=1)).date()})")
        lines.append("=" * 50)

        week_range = range(1, total_weeks + 1) if scope == "이번달" else range(this_week, this_week + 1)

        def format_channel_breakdown(channel_counts: dict) -> str:
            parts = sorted(channel_counts.items(), key=lambda x: x[1], reverse=True)
            return ", ".join(
                f"#{channel_names.get(cid, cid)}: {cnt}"
                for cid, cnt in parts
            )

        for wk in week_range:
            week_start = month_start + timedelta(days=(wk - 1) * 7)
            week_end = week_start + timedelta(days=6)
            lines.append(
                f"\n[{wk}주차] {week_start.date()} ~ {week_end.date()}"
            )

            week_data = stats.get(wk, {})
            if not week_data:
                lines.append("  (메시지 없음)")
                continue

            # 멤버별 총합 기준으로 정렬
            member_totals = [
                (member_id, sum(channel_counts.values()))
                for member_id, channel_counts in week_data.items()
            ]
            member_totals.sort(key=lambda x: x[1], reverse=True)

            for member_id, total in member_totals:
                name = member_names.get(member_id, "알 수 없음")
                breakdown = format_channel_breakdown(week_data[member_id])
                lines.append(f"  {name} ({member_id}): {total}개  [{breakdown}]")

        # 전체 합계도 추가 (멤버별 + 채널별 합계 둘 다)
        lines.append("\n" + "=" * 50)
        lines.append("전체 기간 합계 (멤버별)")
        total_per_member = defaultdict(lambda: defaultdict(int))
        total_per_channel = defaultdict(int)
        for wk_data in stats.values():
            for member_id, channel_counts in wk_data.items():
                for channel_id, cnt in channel_counts.items():
                    total_per_member[member_id][channel_id] += cnt
                    total_per_channel[channel_id] += cnt

        member_grand_totals = [
            (member_id, sum(channel_counts.values()))
            for member_id, channel_counts in total_per_member.items()
        ]
        member_grand_totals.sort(key=lambda x: x[1], reverse=True)

        for member_id, total in member_grand_totals:
            name = member_names.get(member_id, "알 수 없음")
            breakdown = format_channel_breakdown(total_per_member[member_id])
            lines.append(f"  {name} ({member_id}): {total}개  [{breakdown}]")

        lines.append("\n" + "-" * 50)
        lines.append("전체 기간 합계 (채널별)")
        for channel_id, cnt in sorted(
            total_per_channel.items(), key=lambda x: x[1], reverse=True
        ):
            lines.append(f"  #{channel_names.get(channel_id, channel_id)}: {cnt}개")

        # 6. 파일로 저장 후 전송
        filename = f"weekly_stats_{scope}_{start.date()}_{(end - timedelta(seconds=1)).date()}.txt"
        content = "\n".join(lines)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

        await ctx.send(
            file=discord.File(filename),
            content="집계가 완료됐어요!",
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(WeeklyStats(bot))