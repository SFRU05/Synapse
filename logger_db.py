import sqlite3

DB_FILENAME = "log_channel.db"

def ensure_db():
    """DB 및 테이블 초기화 (Context Manager 활용)"""
    with sqlite3.connect(DB_FILENAME) as conn:
        c = conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS log_channel (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)"
        )

def set_log_channel(guild_id: int, channel_id: int):
    """데이터 삽입 및 업데이트"""
    with sqlite3.connect(DB_FILENAME) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO log_channel (guild_id, channel_id) VALUES (?, ?)",
            (guild_id, channel_id)
        )

def get_log_channel_id(guild_id: int):
    """데이터 조회"""
    with sqlite3.connect(DB_FILENAME) as conn:
        c = conn.cursor()
        c.execute("SELECT channel_id FROM log_channel WHERE guild_id = ?", (guild_id,))
        row = c.fetchone()
        return row[0] if row else None