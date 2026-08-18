
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
        - weekly: 최근 7일 [(날짜, 요일라벨, count), ...] (오래된 날짜 -> 오늘 순)
        """
        user_id, guild_id = str(user_id), str(guild_id)

        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT level, exp, total_messages FROM users WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            )
            row = await cur.fetchone()
            level, exp, total_messages = row if row else (0, 0, 0)

            weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]
            weekly = []
            today_count = 0
            week_total = 0

            for i in range(6, -1, -1):  # 6일 전 -> 오늘
                day = datetime.now() - timedelta(days=i)
                date_str = day.strftime("%Y-%m-%d")
                cur2 = await db.execute(
                    "SELECT count FROM daily_messages WHERE user_id=? AND guild_id=? AND date=?",
                    (user_id, guild_id, date_str)
                )
                r = await cur2.fetchone()
                count = r[0] if r else 0
                label = weekday_kr[day.weekday()]
                weekly.append((date_str, label, count))
                week_total += count
                if i == 0:
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
