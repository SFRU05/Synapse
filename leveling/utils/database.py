import os
import aiosqlite
import random
import time
from datetime import datetime, timedelta

DB_PATH = "data/leveling.db"

# 쿨타임(초): 이 시간 안에 여러 메시지를 보내도 exp는 한 번만 지급됨 (도배 방지)
EXP_COOLDOWN = 60
# 메시지 1건당 지급되는 exp 범위
EXP_MIN, EXP_MAX = 15, 25


def required_exp(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100


class LevelDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init(self):
        # 1. DB 파일이 저장될 폴더 경로 자동 생성
        folder_path = os.path.dirname(self.db_path)
        if folder_path:
            os.makedirs(folder_path, exist_ok=True)

        # 2. 데이터베이스 연결 및 테이블 생성
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    level INTEGER NOT NULL DEFAULT 0,
                    exp INTEGER NOT NULL DEFAULT 0,
                    total_messages INTEGER NOT NULL DEFAULT 0,
                    last_message_time REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_messages (
                    user_id TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id, date)
                )
            """)
            await db.commit()

    async def record_message(self, user_id: int, guild_id: int) -> dict:
        user_id, guild_id = str(user_id), str(guild_id)
        today = datetime.now().strftime("%Y-%m-%d")
        now = time.time()

        async with aiosqlite.connect(self.db_path) as db:
            # 1) 일별 채팅수 +1 (upsert)
            await db.execute("""
                INSERT INTO daily_messages (user_id, guild_id, date, count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, guild_id, date)
                DO UPDATE SET count = count + 1
            """, (user_id, guild_id, today))

            # 2) 유저 row 없으면 생성
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id, guild_id, level, exp, total_messages, last_message_time)
                VALUES (?, ?, 0, 0, 0, 0)
            """, (user_id, guild_id))

            cur = await db.execute(
                "SELECT level, exp, total_messages, last_message_time FROM users WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            )
            level, exp, total_messages, last_time = await cur.fetchone()
            total_messages += 1

            leveled_up = False
            gained_exp = 0

            if now - last_time >= EXP_COOLDOWN:
                gained_exp = random.randint(EXP_MIN, EXP_MAX)
                exp += gained_exp
                last_time = now

                # 레벨업 처리 (한 번에 여러 레벨 오를 수도 있으니 while)
                while exp >= required_exp(level):
                    exp -= required_exp(level)
                    level += 1
                    leveled_up = True

            await db.execute("""
                UPDATE users
                SET level=?, exp=?, total_messages=?, last_message_time=?
                WHERE user_id=? AND guild_id=?
            """, (level, exp, total_messages, last_time, user_id, guild_id))

            await db.commit()

        return {"leveled_up": leveled_up, "level": level, "gained_exp": gained_exp}

    async def get_stats(self, user_id: int, guild_id: int) -> dict:
        """
        /레벨 명령어에서 쓸 통계 반환:
        - level, exp, need(다음 레벨까지 필요 exp)
        - total_messages
        - today_count
        - weekly: 이번 주 일~토 [(날짜, 요일라벨, count), ...] (항상 일요일부터 토요일 순서 고정)
        """
        user_id, guild_id = str(user_id), str(guild_id)

        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT level, exp, total_messages FROM users WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            )
            row = await cur.fetchone()
            level, exp, total_messages = row if row else (0, 0, 0)

            weekday_kr = ["일", "월", "화", "수", "목", "금", "토"]
            weekly = []
            today_count = 0
            week_total = 0

            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            # 이번 주 일요일 구하기 (Python weekday(): 월=0 ... 일=6)
            days_since_sunday = (now.weekday() + 1) % 7
            sunday = now - timedelta(days=days_since_sunday)

            for i in range(7):  # 일요일 -> 토요일 고정 순서
                day = sunday + timedelta(days=i)
                date_str = day.strftime("%Y-%m-%d")
                cur2 = await db.execute(
                    "SELECT count FROM daily_messages WHERE user_id=? AND guild_id=? AND date=?",
                    (user_id, guild_id, date_str)
                )
                r = await cur2.fetchone()
                count = r[0] if r else 0
                weekly.append((date_str, weekday_kr[i], count))
                week_total += count
                if date_str == today_str:
                    today_count = count

        return {
            "level": level,
            "exp": exp,
            "need": required_exp(level),
            "total_messages": total_messages,
            "today_count": today_count,
            "week_total": week_total,
            "weekly": weekly,
        }

    async def get_weekly_leaderboard(
        self, guild_id: int, user_id: int, top_n: int = 10, criteria: str = "weekly"
    ) -> dict:
        """
        서버 순위 조회.
        criteria: "weekly"(이번 주 채팅수, 기본값) | "level"(레벨)

        반환값: {
            "top": [{"user_id", "level", "exp", "need", "weekly_count", "rank"}, ...],  # 최대 top_n개
            "me": {..동일 형식.., "rank": int|None},   # rank는 순위표에 아예 없으면 None
            "total_participants": int
        }
        """
        guild_id, user_id = str(guild_id), str(user_id)
        now = datetime.now()
        days_since_sunday = (now.weekday() + 1) % 7
        sunday = now - timedelta(days=days_since_sunday)
        saturday = sunday + timedelta(days=6)
        start_str, end_str = sunday.strftime("%Y-%m-%d"), saturday.strftime("%Y-%m-%d")

        async with aiosqlite.connect(self.db_path) as db:
            # users 테이블에 등록된 모든 유저를 기준으로, 이번 주 채팅수를 LEFT JOIN.
            # (레벨 기준 정렬 시 이번 주에 채팅을 안 한 유저도 순위에 포함되어야 하므로)
            cur = await db.execute("""
                SELECT u.user_id,
                       u.level,
                       u.exp,
                       COALESCE(w.weekly_count, 0) AS weekly_count
                FROM users u
                LEFT JOIN (
                    SELECT user_id, SUM(count) AS weekly_count
                    FROM daily_messages
                    WHERE guild_id = ? AND date BETWEEN ? AND ?
                    GROUP BY user_id
                ) w ON w.user_id = u.user_id
                WHERE u.guild_id = ?
            """, (guild_id, start_str, end_str, guild_id))
            rows = await cur.fetchall()

        entries = [
            {
                "user_id": r[0], "level": r[1], "exp": r[2],
                "need": required_exp(r[1]), "weekly_count": r[3],
            }
            for r in rows
        ]

        # 정렬 기준별 key 함수. 레벨은 동점자를 exp로 한 번 더 구분.
        if criteria == "level":
            sort_key = lambda e: (e["level"], e["exp"])
        else:  # "weekly" (기본값)
            sort_key = lambda e: (e["weekly_count"],)

        entries.sort(key=sort_key, reverse=True)

        # 동점자는 같은 순위를 받고, 다음 순위는 그만큼 건너뛰는 표준 랭킹 방식 (SQL RANK()와 동일)
        prev_key, prev_rank = None, 0
        for idx, e in enumerate(entries, start=1):
            k = sort_key(e)
            if k == prev_key:
                e["rank"] = prev_rank
            else:
                e["rank"] = idx
                prev_rank = idx
                prev_key = k

        top = entries[:top_n]
        me = next((e for e in entries if e["user_id"] == user_id), None)
        if me is None:
            # users 테이블에도 없는 유저 (채팅 기록이 전혀 없음)
            me = {"user_id": user_id, "level": 0, "exp": 0, "need": required_exp(0), "weekly_count": 0, "rank": None}

        return {"top": top, "me": me, "total_participants": len(entries)}