import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import time


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
            f"/ 채널 수: {len(target_channels)}개)"
        )
        status_msg = await ctx.send("수집 준비 중...")

        start_time = time.monotonic()
        last_edit_time = 0.0
        EDIT_INTERVAL = 2.0  # 초 단위. 너무 자주 edit하면 레이트리밋에 걸릴 수 있어 최소 간격을 둠

        completed_channels = []   # 완료된 채널 이름 목록
        channel_durations = []    # 채널별 소요 시간(초) - 평균 내서 예상 시간 계산에 사용
        total_channel_count = len(target_channels)

        def build_status_text(current_channel_name: str, current_date) -> str:
            elapsed = int(time.monotonic() - start_time)

            if channel_durations:
                avg_per_channel = sum(channel_durations) / len(channel_durations)
                remaining_channels = total_channel_count - len(completed_channels) - 1  # 현재 채널 제외
                remaining_channels = max(remaining_channels, 0)
                eta = int(avg_per_channel * remaining_channels)
                eta_text = f"약 {eta}초"
            else:
                eta_text = "계산 중..."

            lines_status = [
                f"수집 중... `#{current_channel_name}` "
                f"({len(completed_channels) + 1}/{total_channel_count}번째 채널) / "
                f"{current_date} 일자 메시지 처리 중",
                f"경과 시간: {elapsed}초 / 예상 남은 시간: {eta_text}",
            ]
            if completed_channels:
                done_text = ", ".join(f"#{n}" for n in completed_channels)
                lines_status.append(f"완료된 채널: {done_text}")

            return "\n".join(lines_status)

        async def update_status(channel_name: str, current_date, force: bool = False):
            nonlocal last_edit_time
            now_t = time.monotonic()
            if not force and (now_t - last_edit_time) < EDIT_INTERVAL:
                return
            last_edit_time = now_t
            try:
                await status_msg.edit(content=build_status_text(channel_name, current_date))
            except discord.HTTPException:
                pass

        total_weeks = week_index(end - timedelta(seconds=1)) if scope == "이번달" else this_week
        start_for_history = start

        # stats[week][member_id][channel_id] = count
        stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        member_names = {}  # id -> 표시 이름 캐시
        channel_names = {}  # id -> 채널 이름 캐시

        # 4. 채널별로 히스토리 순회
        for channel in target_channels:
            channel_names[channel.id] = channel.name
            channel_start_time = time.monotonic()
            await update_status(channel.name, start.date(), force=True)
            try:
                async for message in channel.history(
                    after=start_for_history, before=end, limit=None, oldest_first=True
                ):
                    await update_status(channel.name, message.created_at.date())
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
                pass  # 권한 없는 채널은 스킵
            except discord.HTTPException:
                pass
            finally:
                channel_durations.append(time.monotonic() - channel_start_time)
                completed_channels.append(channel.name)

        elapsed_total = int(time.monotonic() - start_time)
        try:
            await status_msg.edit(
                content=f"수집 완료! (총 소요 시간: {elapsed_total}초) 결과를 정리하고 있어요..."
            )
        except discord.HTTPException:
            pass

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