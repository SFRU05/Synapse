import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "discord_logs.db"


LOG_SETTING_DEFAULTS: dict[str, bool] = {
    "message_delete": True,
    "message_edit": True,

    "member_join": True,
    "member_remove": True,
    "member_role_update": True,

    "member_kick": True,
    "member_ban": True,
    "member_unban": True,

    "role_update": True,
    "role_permissions_update": True,
    "role_create": True,
    "role_delete": True,

    "channel_create": True,
    "channel_delete": True,
    "channel_update": True,
    "channel_permissions_update": True,
}


ALLOWED_SETTING_NAMES = set(LOG_SETTING_DEFAULTS)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db():
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS log_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS log_settings (
                guild_id INTEGER PRIMARY KEY,

                message_delete BOOLEAN DEFAULT 1,
                message_edit BOOLEAN DEFAULT 1,

                member_join BOOLEAN DEFAULT 1,
                member_remove BOOLEAN DEFAULT 1,
                member_role_update BOOLEAN DEFAULT 1,

                member_kick BOOLEAN DEFAULT 1,
                member_ban BOOLEAN DEFAULT 1,
                member_unban BOOLEAN DEFAULT 1,

                role_update BOOLEAN DEFAULT 1,
                role_permissions_update BOOLEAN DEFAULT 1,
                role_create BOOLEAN DEFAULT 1,
                role_delete BOOLEAN DEFAULT 1,

                channel_create BOOLEAN DEFAULT 1,
                channel_delete BOOLEAN DEFAULT 1,
                channel_update BOOLEAN DEFAULT 1,
                channel_permissions_update BOOLEAN DEFAULT 1
            )
            """
        )

        cursor.execute("PRAGMA table_info(log_settings)")

        existing_columns = {
            row["name"]
            for row in cursor.fetchall()
        }

        # 기존 DB에 없는 컬럼 추가
        for column_name, default_value in LOG_SETTING_DEFAULTS.items():
            if column_name in existing_columns:
                continue
            default_number = 1 if default_value else 0

            cursor.execute(
                f"""
                ALTER TABLE log_settings
                ADD COLUMN {column_name}
                BOOLEAN DEFAULT {default_number}
                """
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_log_channel_id(
    guild_id: int
) -> int | None:
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT channel_id
            FROM log_channels
            WHERE guild_id = ?
            """,
            (guild_id,)
        )

        result = cursor.fetchone()

        if result is None:
            return None

        return int(result["channel_id"])

    finally:
        conn.close()


def set_log_channel(
    guild_id: int,
    channel_id: int
):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO log_channels (
                guild_id,
                channel_id
            )
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET channel_id = excluded.channel_id
            """,
            (guild_id, channel_id)
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_log_settings(
    guild_id: int
) -> dict[str, bool]:
    """
    해당 서버의 로그 설정을 반환합니다.
    설정이 없으면 모든 로그를 활성화한 기본값을 반환합니다.
    """
    settings = LOG_SETTING_DEFAULTS.copy()
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM log_settings
            WHERE guild_id = ?
            """,
            (guild_id,)
        )

        result = cursor.fetchone()

        if result is None:
            return settings

        for setting_name in LOG_SETTING_DEFAULTS:
            value = result[setting_name]

            if value is not None:
                settings[setting_name] = bool(value)

        return settings

    finally:
        conn.close()


def ensure_guild_settings(
    guild_id: int
):
    # 서버의 설정 행이 없으면 기본값으로 생성합니다.
    conn = get_connection()

    try:
        cursor = conn.cursor()

        column_names = [
            "guild_id",
            *LOG_SETTING_DEFAULTS.keys()
        ]

        placeholders = ", ".join(
            "?" for _ in column_names
        )

        values = [
            guild_id,
            *[
                int(value)
                for value in LOG_SETTING_DEFAULTS.values()
            ]
        ]

        cursor.execute(
            f"""
            INSERT OR IGNORE INTO log_settings (
                {", ".join(column_names)}
            )
            VALUES ({placeholders})
            """,
            values
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def set_log_setting(
    guild_id: int,
    setting_name: str,
    value: bool
):
    if setting_name not in ALLOWED_SETTING_NAMES:
        raise ValueError(
            f"허용되지 않은 로그 설정입니다: {setting_name}"
        )

    ensure_guild_settings(guild_id)

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            f"""
            UPDATE log_settings
            SET {setting_name} = ?
            WHERE guild_id = ?
            """,
            (int(value), guild_id)
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def update_all_log_settings(
    guild_id: int,
    settings: dict[str, bool]
):
    ensure_guild_settings(guild_id)

    conn = get_connection()

    try:
        cursor = conn.cursor()

        update_parts = []
        values = []

        for setting_name, default_value in (
            LOG_SETTING_DEFAULTS.items()
        ):
            update_parts.append(
                f"{setting_name} = ?"
            )

            values.append(
                int(
                    settings.get(
                        setting_name,
                        default_value
                    )
                )
            )

        values.append(guild_id)

        cursor.execute(
            f"""
            UPDATE log_settings
            SET {", ".join(update_parts)}
            WHERE guild_id = ?
            """,
            values
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()