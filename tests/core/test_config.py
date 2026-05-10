from geekclock.core import config


def test_load_config_empty(temp_config_path):
    config._invalidate_cache()
    cfg = config.load_config()
    assert cfg["schema_version"] == config.CURRENT_SCHEMA_VERSION
    assert cfg["alarms"] == []


def test_add_alarm_generates_id(temp_config_path, sample_alarm):
    config._invalidate_cache()
    alarm = dict(sample_alarm)
    assert "id" not in alarm
    ok = config.add_alarm(alarm)
    assert ok
    assert "id" in alarm
    assert len(alarm["id"]) == 12


def test_add_alarm_persists(temp_config_path, sample_alarm):
    config._invalidate_cache()
    config.add_alarm(dict(sample_alarm))
    config._invalidate_cache()
    alarms = config.get_alarms()
    assert len(alarms) == 1
    assert alarms[0]["name"] == "测试闹钟"


def test_update_alarm_found(temp_config_path, sample_alarm):
    config._invalidate_cache()
    a1 = dict(sample_alarm)
    config.add_alarm(a1)
    alarm_id = a1["id"]
    updated = dict(sample_alarm)
    updated["name"] = "改名后的闹钟"
    ok = config.update_alarm(alarm_id, updated)
    assert ok
    config._invalidate_cache()
    alarms = config.get_alarms()
    assert alarms[0]["name"] == "改名后的闹钟"


def test_update_alarm_not_found(temp_config_path, sample_alarm):
    config._invalidate_cache()
    ok = config.update_alarm("nonexistent", dict(sample_alarm))
    assert not ok


def test_delete_alarm_exists(temp_config_path, sample_alarm):
    config._invalidate_cache()
    a1 = dict(sample_alarm)
    config.add_alarm(a1)
    ok = config.delete_alarm(a1["id"])
    assert ok
    assert config.get_alarms() == []


def test_delete_alarm_not_exists(temp_config_path):
    config._invalidate_cache()
    ok = config.delete_alarm("nonexistent")
    assert ok


def test_toggle_alarm(temp_config_path, sample_alarm):
    config._invalidate_cache()
    a1 = dict(sample_alarm)
    config.add_alarm(a1)
    ok = config.toggle_alarm(a1["id"], False)
    assert ok
    config._invalidate_cache()
    assert config.get_alarms()[0]["enabled"] is False


def test_toggle_alarm_not_found(temp_config_path):
    config._invalidate_cache()
    ok = config.toggle_alarm("nonexistent", True)
    assert not ok


def test_get_group_color_deterministic():
    c1 = config.get_group_color("工作")
    c2 = config.get_group_color("工作")
    assert c1 == c2


def test_get_group_color_different_groups():
    c1 = config.get_group_color("工作")
    c2 = config.get_group_color("健康")
    assert c1 != c2


def test_get_groups_sorted(temp_config_path, sample_alarm):
    config._invalidate_cache()
    config.add_alarm(dict(sample_alarm, group="B组"))
    config.add_alarm(dict(sample_alarm, group="A组"))
    config.add_alarm(dict(sample_alarm, group="默认"))
    groups = config.get_groups()
    assert groups[0] == "默认"
    assert "A组" in groups
    assert "B组" in groups


def test_set_all_alarms_enabled(temp_config_path, sample_alarm):
    config._invalidate_cache()
    config.add_alarm(dict(sample_alarm))
    config.add_alarm(dict(sample_alarm))
    config.set_all_alarms_enabled(False)
    config._invalidate_cache()
    for a in config.get_alarms():
        assert a["enabled"] is False


def test_toggle_group(temp_config_path, sample_alarm):
    config._invalidate_cache()
    config.add_alarm(dict(sample_alarm, group="G1"))
    config.add_alarm(dict(sample_alarm, group="G1"))
    config.toggle_group("G1", False)
    config._invalidate_cache()
    for a in config.get_alarms():
        assert a["enabled"] is False


def test_global_settings_default(temp_config_path):
    config._invalidate_cache()
    s = config.get_global_settings()
    assert "dnd_enabled" in s
    assert "keep_alive" in s


def test_update_global_settings_nested(temp_config_path):
    config._invalidate_cache()
    config.update_global_settings({"dnd_enabled": True})
    config._invalidate_cache()
    assert config.get_global_settings()["dnd_enabled"] is True


def test_user_nickname(temp_config_path):
    config._invalidate_cache()
    assert config.get_user_nickname() == ""
    config.set_user_nickname("大佬")
    config._invalidate_cache()
    assert config.get_user_nickname() == "大佬"


def test_floating_clock_settings(temp_config_path):
    config._invalidate_cache()
    s = config.get_floating_clock_settings()
    assert "enabled" in s
    assert "mode" in s


def test_timer_settings(temp_config_path):
    config._invalidate_cache()
    s = config.get_timer_settings()
    assert "enabled" in s
    assert "mode" in s
