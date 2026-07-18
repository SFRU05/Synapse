import json
import os

# 이 파일과 같은 폴더에 settings.json 생성
_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

VALID_FEATURES = ("custom", "unicode")


def _load() -> dict:
    if not os.path.exists(_PATH):
        return {}
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict):
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_enabled(guild_id: int, feature: str = "custom", default: bool = False) -> bool:
    """feature: "custom"(커스텀 이모지) 또는 "unicode"(기본 이모지)"""
    data = _load()
    guild_data = data.get(str(guild_id), {})
    return guild_data.get(feature, default)


def set_enabled(guild_id: int, feature: str, enabled: bool):
    """feature: "custom"(커스텀 이모지) 또는 "unicode"(기본 이모지)"""
    data = _load()
    guild_data = data.setdefault(str(guild_id), {})
    guild_data[feature] = enabled
    _save(data)