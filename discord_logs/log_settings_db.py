import sqlite3

DB_PATH = "discord_logs.db"


def ensure_db():
    """데이터베이스 테이블 생성"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 로그 채널 설정 테이블
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS log_channels
                   (
                       guild_id
                       INTEGER
                       PRIMARY
                       KEY,
                       channel_id
                       INTEGER
                       NOT
                       NULL
                   )
                   """)

    # 로그 종류별 설정 테이블
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS log_settings
                   (
                       guild_id
                       INTEGER
                       PRIMARY
                       KEY,
                       message_delete
                       BOOLEAN
                       DEFAULT
                       1,
                       message_edit
                       BOOLEAN
                       DEFAULT
                       1,
                       member_join
                       BOOLEAN
                       DEFAULT
                       1,
                       member_remove
                       BOOLEAN
                       DEFAULT
                       1,
                       member_role_update
                       BOOLEAN
                       DEFAULT
                       1,
                       role_update
                       BOOLEAN
                       DEFAULT
                       1,
                       role_create
                       BOOLEAN
                       DEFAULT
                       1,
                       role_delete
                       BOOLEAN
                       DEFAULT
                       1,
                       channel_create
                       BOOLEAN
                       DEFAULT
                       1,
                       channel_delete
                       BOOLEAN
                       DEFAULT
                       1,
                       channel_update
                       BOOLEAN
                       DEFAULT
                       1
                   )
                   """)

    # 새로운 컬럼 추가 (기존 테이블에)
    try:
        cursor.execute("ALTER TABLE log_settings ADD COLUMN role_create BOOLEAN DEFAULT 1")
    except:
        pass

    try:
        cursor.execute("ALTER TABLE log_settings ADD COLUMN role_delete BOOLEAN DEFAULT 1")
    except:
        pass

    conn.commit()
    conn.close()


def get_log_channel_id(guild_id: int) -> int | None:
    """로그 채널 ID 가져오기"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM log_channels WHERE guild_id = ?", (guild_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def set_log_channel(guild_id: int, channel_id: int):
    """로그 채널 설정"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO log_channels (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel_id))
    conn.commit()
    conn.close()


def get_log_settings(guild_id: int) -> dict:
    """서버의 로그 설정 가져오기"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM log_settings WHERE guild_id = ?", (guild_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        # 기본값 반환
        return {
            "message_delete": True,
            "message_edit": True,
            "member_join": True,
            "member_remove": True,
            "member_role_update": True,
            "role_update": True,
            "role_create": True,
            "role_delete": True,
            "channel_create": True,
            "channel_delete": True,
            "channel_update": True,
        }

    # 기존 데이터와 새 필드 호환
    return {
        "message_delete": bool(result[1]) if len(result) > 1 else True,
        "message_edit": bool(result[2]) if len(result) > 2 else True,
        "member_join": bool(result[3]) if len(result) > 3 else True,
        "member_remove": bool(result[4]) if len(result) > 4 else True,
        "member_role_update": bool(result[5]) if len(result) > 5 else True,
        "role_update": bool(result[6]) if len(result) > 6 else True,
        "role_create": bool(result[7]) if len(result) > 7 else True,
        "role_delete": bool(result[8]) if len(result) > 8 else True,
        "channel_create": bool(result[9]) if len(result) > 9 else True,
        "channel_delete": bool(result[10]) if len(result) > 10 else True,
        "channel_update": bool(result[11]) if len(result) > 11 else True,
    }


def set_log_setting(guild_id: int, setting_name: str, value: bool):
    """특정 로그 설정 변경"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 기존 설정이 없으면 기본값으로 생성
    cursor.execute("SELECT * FROM log_settings WHERE guild_id = ?", (guild_id,))
    if not cursor.fetchone():
        cursor.execute("""
                       INSERT INTO log_settings (guild_id)
                       VALUES (?)
                       """, (guild_id,))

    # 설정 업데이트
    cursor.execute(f"UPDATE log_settings SET {setting_name} = ? WHERE guild_id = ?", (value, guild_id))
    conn.commit()
    conn.close()


def update_all_log_settings(guild_id: int, settings: dict):
    """모든 로그 설정 한 번에 업데이트"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 기존 설정이 없으면 생성
    cursor.execute("SELECT * FROM log_settings WHERE guild_id = ?", (guild_id,))
    if not cursor.fetchone():
        cursor.execute("""
                       INSERT INTO log_settings (guild_id)
                       VALUES (?)
                       """, (guild_id,))

    # 모든 설정 업데이트
    cursor.execute("""
                   UPDATE log_settings
                   SET message_delete     = ?,
                       message_edit       = ?,
                       member_join        = ?,
                       member_remove      = ?,
                       member_role_update = ?,
                       role_update        = ?,
                       role_create        = ?,
                       role_delete        = ?,
                       channel_create     = ?,
                       channel_delete     = ?,
                       channel_update     = ?
                   WHERE guild_id = ?
                   """, (
                       settings.get("message_delete", True),
                       settings.get("message_edit", True),
                       settings.get("member_join", True),
                       settings.get("member_remove", True),
                       settings.get("member_role_update", True),
                       settings.get("role_update", True),
                       settings.get("role_create", True),
                       settings.get("role_delete", True),
                       settings.get("channel_create", True),
                       settings.get("channel_delete", True),
                       settings.get("channel_update", True),
                       guild_id
                   ))
    conn.commit()
    conn.close()