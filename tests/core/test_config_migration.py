import json

from geekclock.core import config


def test_migrate_v0_to_v1(temp_config_path):
    config._invalidate_cache()
    old = {
        "global": {"dnd_enabled": True},
        "alarms": [{"id": "test1", "name": "老闹钟"}],
    }
    temp_config_path.write_text(json.dumps(old), encoding="utf-8")
    config._invalidate_cache()
    cfg = config.load_config()
    assert cfg["schema_version"] == config.CURRENT_SCHEMA_VERSION
    assert cfg["global"]["dnd_enabled"] is True
    assert len(cfg["alarms"]) == 1


def test_current_version_no_migration(temp_config_path):
    config._invalidate_cache()
    current = config.DEFAULT_CONFIG.copy()
    temp_config_path.write_text(json.dumps(current), encoding="utf-8")
    config._invalidate_cache()
    cfg = config.load_config()
    assert cfg["schema_version"] == config.CURRENT_SCHEMA_VERSION


def test_corrupt_json_falls_back_to_default(temp_config_path):
    config._invalidate_cache()
    temp_config_path.write_text("{this is not valid json", encoding="utf-8")
    config._invalidate_cache()
    cfg = config.load_config()
    assert cfg["schema_version"] == config.CURRENT_SCHEMA_VERSION
    assert cfg["alarms"] == []


def test_backup_created_on_migration(temp_config_path):
    config._invalidate_cache()
    old = {
        "global": {},
        "alarms": [],
    }
    temp_config_path.write_text(json.dumps(old), encoding="utf-8")
    config._invalidate_cache()
    config.load_config()
    backup = temp_config_path.parent / "alarms.json.v0.bak"
    assert backup.exists()
