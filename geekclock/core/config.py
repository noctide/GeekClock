import copy
import json
import logging
import os
import sys
import uuid
from pathlib import Path

from geekclock.system.resources import project_root

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1

MIGRATORS = {
    0: lambda cfg: _migrate_v0_to_v1(cfg),
}


def _migrate_v0_to_v1(cfg: dict) -> dict:
    cfg["schema_version"] = 1
    return cfg


def _backup_before_migration(cfg: dict, from_version: int) -> None:
    import shutil
    backup_path = CONFIG_PATH.with_suffix(f".json.v{from_version}.bak")
    try:
        shutil.copy2(CONFIG_PATH, backup_path)
        logger.info(f"已备份配置到 {backup_path}")
    except OSError as e:
        logger.warning(f"备份配置失败：{e}")


_config_cache: dict | None = None

GROUP_COLORS = [
    "#5DCAA5", "#AFA9EC", "#FAC775", "#E24B4A", "#5095E8",
    "#F08D4A", "#9C27B0", "#00BCD4", "#795548", "#607D8B",
]


def get_group_color(group_name: str) -> str:
    import hashlib
    idx = int(hashlib.md5(group_name.encode()).hexdigest(), 16) % len(GROUP_COLORS)
    return GROUP_COLORS[idx]


def _get_config_dir() -> Path:
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        config_dir = Path(base) / "GeekClock"
    else:
        config_dir = project_root()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


CONFIG_PATH = _get_config_dir() / "alarms.json"

DEFAULT_CONFIG = {
    "schema_version": CURRENT_SCHEMA_VERSION,
    "global": {
        "dnd_enabled": False,
        "dnd_start": "22:00",
        "dnd_end": "08:00",
        "notification": {
            "snooze_presets": [5, 15, 30, 60],
            "tomorrow_morning_time": "09:00",
            "today_later_offset_hours": 2,
        },
        "floating_clock": {
            "enabled": False,
            "mode": "clock",
            "opacity": 0.85,
            "position": [None, None],
            "locked": False,
        },
        "timer": {
            "enabled": False,
            "mode": "countdown",
            "opacity": 0.85,
            "position": [None, None],
            "always_on_top": True,
            "countdown_seconds": 900,
            "countdown_audio": "",
            "countdown_volume": 0.6,
        },
        "autostart": False,
        "keep_alive": {
            "enabled": False,
            "interval_minutes": 10,
            "volume": 0.0,
            "active_from": "00:00",
            "active_to": "23:59",
        },
    },
    "alarms": [],
}


def _invalidate_cache() -> None:
    global _config_cache
    _config_cache = None


def load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    if not CONFIG_PATH.exists():
        logger.warning(f"配置文件不存在，使用默认配置：{CONFIG_PATH}")
        _config_cache = copy.deepcopy(DEFAULT_CONFIG)
        return _config_cache
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            _config_cache = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"配置文件读取失败：{e}，使用默认配置")
        _config_cache = copy.deepcopy(DEFAULT_CONFIG)
        return _config_cache

    version = _config_cache.get("schema_version", 0)
    while version < CURRENT_SCHEMA_VERSION:
        migrator = MIGRATORS.get(version)
        if not migrator:
            logger.error(f"未找到从版本 {version} 的迁移函数")
            break
        _backup_before_migration(_config_cache, version)
        _config_cache = migrator(_config_cache)
        version = _config_cache["schema_version"]
        save_config(_config_cache)

    logger.info(f"已加载 {len(_config_cache.get('alarms', []))} 个闹钟配置")
    return _config_cache


def save_config(config: dict) -> bool:
    global _config_cache
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        _config_cache = config
        logger.info("配置已保存")
        return True
    except OSError as e:
        logger.error(f"配置文件写入失败：{e}")
        _invalidate_cache()
        return False


def get_alarms() -> list:
    return load_config().get("alarms", [])


def get_global_settings() -> dict:
    return load_config().get("global", DEFAULT_CONFIG["global"])


def get_notification_settings() -> dict:
    settings = get_global_settings().get("notification", {})
    defaults = DEFAULT_CONFIG["global"]["notification"]
    return {
        "snooze_presets": settings.get("snooze_presets", defaults["snooze_presets"]),
        "tomorrow_morning_time": settings.get("tomorrow_morning_time", defaults["tomorrow_morning_time"]),
        "today_later_offset_hours": settings.get("today_later_offset_hours", defaults["today_later_offset_hours"]),
    }


def add_alarm(alarm: dict) -> bool:
    if "id" not in alarm:
        alarm["id"] = uuid.uuid4().hex[:12]
    alarm.setdefault("group", "默认")
    cfg = load_config()
    cfg.setdefault("alarms", []).append(alarm)
    return save_config(cfg)


def update_alarm(alarm_id: str, alarm: dict) -> bool:
    alarm["id"] = alarm_id
    cfg = load_config()
    alarms = cfg.get("alarms", [])
    for i, a in enumerate(alarms):
        if a.get("id") == alarm_id:
            alarms[i] = alarm
            cfg["alarms"] = alarms
            return save_config(cfg)
    logger.warning(f"未找到闹钟 id={alarm_id}，无法更新")
    return False


def delete_alarm(alarm_id: str) -> bool:
    cfg = load_config()
    cfg["alarms"] = [a for a in cfg.get("alarms", []) if a.get("id") != alarm_id]
    return save_config(cfg)


def toggle_alarm(alarm_id: str, enabled: bool) -> bool:
    cfg = load_config()
    for a in cfg.get("alarms", []):
        if a.get("id") == alarm_id:
            a["enabled"] = enabled
            return save_config(cfg)
    return False


def get_groups() -> list[str]:
    groups = set(a.get("group", "默认") for a in get_alarms())
    return sorted(groups, key=lambda g: (g != "默认", g))


def toggle_group(group_name: str, enabled: bool) -> bool:
    cfg = load_config()
    for a in cfg.get("alarms", []):
        if a.get("group", "默认") == group_name:
            a["enabled"] = enabled
    return save_config(cfg)


def get_keep_alive_settings() -> dict:
    settings = get_global_settings().get("keep_alive", {})
    defaults = DEFAULT_CONFIG["global"]["keep_alive"]
    return {
        "enabled": settings.get("enabled", defaults["enabled"]),
        "interval_minutes": settings.get("interval_minutes", defaults["interval_minutes"]),
        "volume": settings.get("volume", defaults["volume"]),
        "active_from": settings.get("active_from", defaults["active_from"]),
        "active_to": settings.get("active_to", defaults["active_to"]),
    }


def update_keep_alive_settings(updates: dict) -> bool:
    cfg = load_config()
    cfg.setdefault("global", {}).setdefault("keep_alive", {})
    cfg["global"]["keep_alive"].update(updates)
    return save_config(cfg)


def set_all_alarms_enabled(enabled: bool) -> bool:
    cfg = load_config()
    for a in cfg.get("alarms", []):
        a["enabled"] = enabled
    return save_config(cfg)


def get_floating_clock_settings() -> dict:
    settings = get_global_settings().get("floating_clock", {})
    defaults = DEFAULT_CONFIG["global"]["floating_clock"]
    return {
        "enabled": settings.get("enabled", defaults["enabled"]),
        "mode": settings.get("mode", defaults["mode"]),
        "opacity": settings.get("opacity", defaults["opacity"]),
        "position": settings.get("position", defaults["position"]),
        "locked": settings.get("locked", defaults["locked"]),
    }


def update_floating_clock_settings(updates: dict) -> bool:
    cfg = load_config()
    cfg.setdefault("global", {}).setdefault("floating_clock", {})
    cfg["global"]["floating_clock"].update(updates)
    return save_config(cfg)


def get_user_nickname() -> str:
    return get_global_settings().get("nickname", "")


def set_user_nickname(nickname: str) -> bool:
    cfg = load_config()
    cfg.setdefault("global", {})["nickname"] = nickname
    return save_config(cfg)


def get_timer_settings() -> dict:
    settings = get_global_settings().get("timer", {})
    defaults = DEFAULT_CONFIG["global"]["timer"]
    return {
        "enabled": settings.get("enabled", defaults["enabled"]),
        "mode": settings.get("mode", defaults["mode"]),
        "opacity": settings.get("opacity", defaults["opacity"]),
        "position": settings.get("position", defaults["position"]),
        "always_on_top": settings.get("always_on_top", defaults["always_on_top"]),
        "countdown_seconds": settings.get("countdown_seconds", defaults["countdown_seconds"]),
        "countdown_audio": settings.get("countdown_audio", defaults["countdown_audio"]),
        "countdown_volume": settings.get("countdown_volume", defaults["countdown_volume"]),
    }


def update_timer_settings(updates: dict) -> bool:
    cfg = load_config()
    cfg.setdefault("global", {}).setdefault("timer", {})
    cfg["global"]["timer"].update(updates)
    return save_config(cfg)


def update_global_settings(updates: dict) -> bool:
    cfg = load_config()
    g = cfg.setdefault("global", {})
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(g.get(key), dict):
            g[key].update(value)
        else:
            g[key] = value
    return save_config(cfg)
