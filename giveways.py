import discord
import sqlite3
import random
import asyncio
import re
from datetime import datetime, timedelta, timezone

DB_PATH = "giveaway.db"

# 시간 입력 "1d2h3m", "150" 등 파싱
def parse_time_to_minutes(time_text: str) -> int:
    total = 0
    pattern = r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m?)?$'
    # 공백, 소문자만 허용
    text = time_text.lower().replace(" ", "")
    match = re.fullmatch(pattern, text)
    if match:
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        mins = int(match.group(3) or 0)
        total = days*1440 + hours*60 + mins
    else:
        # fallback: 숫자만 있으면 분으로 취급
        try:
            total = int(time_text)
        except ValueError:
            total = 0
    return total

# DB에서 읽은 datetime을 "timezone-aware(UTC)"로
def parse_utc(dt_txt):
    txt = str(dt_txt).split('.')[0]
    dt = datetime.strptime(txt, '%Y-%m-%d %H:%M:%S')
    return dt.replace(tzinfo=timezone.utc)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                time INTEGER,
                winners INTEGER,
                message_id INTEGER,
                channel_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giveaway_id INTEGER,
                user_id INTEGER,
                UNIQUE(giveaway_id, user_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_winners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giveaway_id INTEGER,
                winner_user_id INTEGER
            )
        """)
        conn.commit()

init_db()

def save_giveaway(user_id: int, name: str, time: int, winners: int, message_id=None, channel_id=None):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO giveaways (user_id, name, time, winners, message_id, channel_id) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, time, winners, message_id, channel_id)
        )
        conn.commit()
        return cur.lastrowid

def set_giveaway_message(giveaway_id, message_id, channel_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE giveaways SET message_id=?, channel_id=? WHERE id=?",
            (message_id, channel_id, giveaway_id)
        )
        conn.commit()

def end_giveaway(giveaway_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE giveaways SET ended=1 WHERE id=?", (giveaway_id,)
        )
        conn.commit()

def get_giveaway_by_id(giveaway_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, time, winners, user_id, message_id, channel_id, created_at, ended FROM giveaways WHERE id=?",
            (giveaway_id,)
        )
        return cur.fetchone()

def get_active_giveaways():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, time, winners, user_id, message_id, channel_id, created_at FROM giveaways WHERE ended = 0"
        )
        return cur.fetchall()

def get_all_giveaways():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, time, winners, user_id, created_at, ended FROM giveaways ORDER BY id DESC"
        )
        return cur.fetchall()

def add_participant(giveaway_id, user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT OR IGNORE INTO giveaway_participants (giveaway_id, user_id) VALUES (?, ?)",
                (giveaway_id, user_id)
            )
            conn.commit()
        except Exception as e:
            print(f"Failed to add participant: {e}")

def get_participants(giveaway_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id FROM giveaway_participants WHERE giveaway_id=?",
            (giveaway_id,)
        )
        return [row[0] for row in cur.fetchall()]

def save_winners(giveaway_id, winner_list):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM giveaway_winners WHERE giveaway_id=?", (giveaway_id,))
        cur.executemany(
            "INSERT INTO giveaway_winners (giveaway_id, winner_user_id) VALUES (?, ?)",
            [(giveaway_id, user_id) for user_id in winner_list]
        )
        conn.commit()

def get_winners(giveaway_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT winner_user_id FROM giveaway_winners WHERE giveaway_id=?", (giveaway_id,))
        return [row[0] for row in cur.fetchall()]

async def scheduled_giveaway_announce(bot):
    await bot.wait_until_ready()
    active = get_active_giveaways()
    for row in active:
        id, name, time_m, winners, user_id, msg_id, ch_id, created_at = row
        created_dt = parse_utc(created_at)
        finish_time = created_dt + timedelta(minutes=int(time_m))
        now = datetime.now(timezone.utc)
        remain = (finish_time - now).total_seconds()
        if remain > 0:
            asyncio.create_task(
                delayed_announce(bot, id, remain)
            )
        else:
            asyncio.create_task(
                delayed_announce(bot, id, 2)
            )

class GiveawayCancelView(discord.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=60)  # ephemeral 이라 1분쯤이면 충분
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="참여 취소하기", style=discord.ButtonStyle.secondary, custom_id="giveaway_cancel_btn")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM giveaway_participants WHERE giveaway_id=? AND user_id=?",
                (self.giveaway_id, interaction.user.id)
            )
            conn.commit()
        giveaway = get_giveaway_by_id(self.giveaway_id)
        p = get_participants(self.giveaway_id)
        count = len(p)
        created_dt = parse_utc(giveaway[7])
        expire_dt = created_dt + timedelta(minutes=int(giveaway[2]))
        ts = int(expire_dt.timestamp())
        embed = discord.Embed(
            title=f"🎉 {giveaway[1]}",
            description=(f"당첨 인원: {giveaway[3]}명\n"
                        f"마감 시각: <t:{ts}:F> (<t:{ts}:R>)\n"
                        f"현재 참여 인원: **{count}명**"),
            color=discord.Color.blurple()
        )
        msg_id, ch_id = giveaway[5], giveaway[6]
        try:
            if interaction.guild and msg_id and ch_id:
                channel = interaction.guild.get_channel(ch_id)
                if channel:
                    msg = await channel.fetch_message(msg_id)
                    msg_view = GiveawayJoinView(self.giveaway_id)
                    await msg.edit(embed=embed, view=msg_view)
        except Exception as e:
            print("메시지 수정 오류:", e)
        await interaction.response.send_message("참여가 취소되었습니다.", ephemeral=True)

class GiveawayJoinView(discord.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="참여하기", style=discord.ButtonStyle.primary, custom_id="giveaway_join_btn")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = get_giveaway_by_id(self.giveaway_id)
        if not giveaway or giveaway[8]:
            await interaction.response.send_message("이 이벤트는 이미 종료되었습니다.", ephemeral=True)
            return
        p = get_participants(self.giveaway_id)
        if interaction.user.id in p:
            view = GiveawayCancelView(self.giveaway_id)
            await interaction.response.send_message(
                "이미 참여하셨습니다.\n참여를 취소하려면 아래 버튼을 눌러주세요.",
                ephemeral=True,
                view=view
            )
            return
        add_participant(self.giveaway_id, interaction.user.id)
        p = get_participants(self.giveaway_id)
        count = len(p)
        created_dt = parse_utc(giveaway[7])
        expire_dt = created_dt + timedelta(minutes=int(giveaway[2]))
        ts = int(expire_dt.timestamp())
        embed = discord.Embed(
            title=f"🎉 {giveaway[1]}",
            description=(f"이벤트 시간: {giveaway[2]}분\n"
                         f"당첨 인원: {giveaway[3]}명\n"
                         f"마감 시각: <t:{ts}:F> (<t:{ts}:R>)\n"
                         f"현재 참여 인원: **{count}명**"),
            color=discord.Color.blurple()
        )
        msg_id, ch_id = giveaway[5], giveaway[6]
        if msg_id and ch_id:
            guild = interaction.guild
            if guild:
                channel = guild.get_channel(ch_id)
                if channel:
                    try:
                        msg = await channel.fetch_message(msg_id)
                        await msg.edit(embed=embed, view=self)
                    except Exception as e:
                        print("메시지 수정 오류:", e)
        await interaction.response.send_message(f"참여 완료! (현재 {count}명)", ephemeral=True)

class GiveawayRerollView(discord.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="재추첨", style=discord.ButtonStyle.danger, custom_id="giveaway_reroll_btn")
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = get_giveaway_by_id(self.giveaway_id)
        if not giveaway or not giveaway[8]:
            await interaction.response.send_message("이벤트가 종료되지 않았거나 찾을 수 없습니다.", ephemeral=True)
            return

        host_id = giveaway[4]
        if interaction.user.id != host_id:
            await interaction.response.send_message("재추첨은 개최자만 누를 수 있습니다.", ephemeral=True)
            return

        all_participants = set(get_participants(self.giveaway_id))
        prev_winners = set(get_winners(self.giveaway_id))
        candidates = list(all_participants - prev_winners)
        if not candidates:
            await interaction.response.send_message("재추첨 대상이 없습니다. (모든 참가자가 이미 당첨됨)", ephemeral=True)
            return

        winners_n = min(giveaway[3], len(candidates))
        new_winners = random.sample(candidates, winners_n)
        save_winners(self.giveaway_id, new_winners)

        created_dt = parse_utc(giveaway[7])
        expire_dt = created_dt + timedelta(minutes=int(giveaway[2]))
        ts = int(expire_dt.timestamp())
        embed = discord.Embed(
            title=f"🎉 {giveaway[1]} - 재추첨 당첨자 발표!",
            description=(
                f"**개최자:** <@{host_id}>\n"
                f"마감 시각: <t:{ts}:F> (<t:{ts}:R>)\n\n"
                f"**재추첨 당첨자:** {', '.join(f'<@{uid}>' for uid in new_winners)}"
            ),
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send("재추첨 완료!", ephemeral=True)

async def delayed_announce(bot, giveaway_id, wait_sec):
    await asyncio.sleep(wait_sec)
    giveaway = get_giveaway_by_id(giveaway_id)
    if not giveaway or giveaway[8]: return  # 이미 끝
    _, name, time_m, winners, host_id, msg_id, ch_id, created_at, _ = giveaway
    p = get_participants(giveaway_id)

    if len(p) < 1:
        winner_mentions = "참여자가 없어 추첨이 없습니다."
        winner_ids = []
    else:
        winners_n = min(winners, len(p))
        chosen = random.sample(p, winners_n)
        winner_mentions = ", ".join(f"<@{uid}>" for uid in chosen)
        winner_ids = chosen
        save_winners(giveaway_id, winner_ids)

    created_dt = parse_utc(created_at)
    expire_dt = created_dt + timedelta(minutes=int(time_m))
    ts = int(expire_dt.timestamp())
    embed = discord.Embed(
        title=f"🎉 {name} - 당첨자 발표!",
        description=(
            f"**개최자:** <@{host_id}>\n"
            f"마감 시각: <t:{ts}:F> (<t:{ts}:R>)\n\n"
            f"**당첨자:** {winner_mentions}"
        ),
        color=discord.Color.gold()
    )
    view = GiveawayRerollView(giveaway_id) if winner_ids else None

    for guild in bot.guilds:
        channel = guild.get_channel(ch_id)
        if channel:
            try:
                if msg_id:
                    old = await channel.fetch_message(msg_id)
                    await old.edit(view=None)
            except Exception:
                pass
            await channel.send(embed=embed, view=view)
            break
    end_giveaway(giveaway_id)

class GiveawayModal(discord.ui.Modal, title="Giveaway 등록"):
    name = discord.ui.TextInput(
        label="이름", placeholder="이벤트 이름을 입력하세요", required=True, max_length=50)
    time = discord.ui.TextInput(
        label="시간(예: 1d2h3m, 10m, 3h, 5)", placeholder="예: 1d2h3m, 10m 등", required=True, max_length=20)
    winners = discord.ui.TextInput(
        label="당첨 인원", placeholder="예: 3", required=True, max_length=3)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minute = parse_time_to_minutes(self.time.value)
            winners_int = int(self.winners.value)
            if minute < 1 or winners_int < 1:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("시간(1분 이상)과 당첨 인원(1명 이상)을 제대로 입력하세요.", ephemeral=True)
            return

        give_id = save_giveaway(
            user_id=interaction.user.id,
            name=self.name.value,
            time=minute,
            winners=winners_int,
            message_id=None,
            channel_id=None
        )

        now_dt = datetime.now(timezone.utc)
        expire_dt = now_dt + timedelta(minutes=minute)
        ts = int(expire_dt.timestamp())

        embed = discord.Embed(
            title=f"🎉 {self.name.value}",
            description=(
                f"**개최자:** <@{interaction.user.id}>\n"
                f"당첨 인원: {self.winners.value}명\n"
                f"마감 시각: <t:{ts}:F> (<t:{ts}:R>)\n"
                f"현재 참여 인원: **0명**"
            ),
            color=discord.Color.blurple()
        )
        view = GiveawayJoinView(give_id)
        msg = await interaction.channel.send(embed=embed, view=view)
        set_giveaway_message(give_id, msg.id, msg.channel.id)
        bot = interaction.client
        asyncio.create_task(delayed_announce(bot, give_id, minute*60))
        await interaction.response.send_message("이벤트가 생성되었습니다!", ephemeral=True)

@discord.app_commands.command(name="이벤트", description="Giveaway 정보를 등록합니다.")
async def giveway_slash(interaction: discord.Interaction):
    await interaction.response.send_modal(GiveawayModal())

@discord.app_commands.command(name="이벤트목록", description="모든 Giveaway를 확인합니다.")
async def giveway_list_slash(interaction: discord.Interaction):
    data = get_all_giveaways()
    if not data:
        await interaction.response.send_message("등록된 giveaway가 없습니다.", ephemeral=True)
        return

    desc = ""
    for i, (id, name, time, winners, user_id, created_at, ended) in enumerate(data, 1):
        status = "종료됨" if ended else "진행중"
        desc += f"**{i}.** {name} | {time}분 | {winners}명 | 개최자: <@{user_id}> ({created_at}) [{status}]\n"
    embed = discord.Embed(title="Giveaway 목록", description=desc, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)