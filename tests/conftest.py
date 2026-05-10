import shutil
import tempfile
from pathlib import Path

import pytest

import geekclock.core.config as config_module


@pytest.fixture
def temp_config_path(monkeypatch):
    """Redirect config to a temp file, isolated from real user data."""
    tmp_dir = Path(tempfile.mkdtemp())
    tmp = tmp_dir / "alarms.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp)
    config_module._config_cache = None
    yield tmp
    config_module._config_cache = None
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def sample_alarm():
    return {
        "name": "测试闹钟",
        "group": "测试分组",
        "enabled": True,
        "trigger_type": "interval",
        "trigger_args": {"minutes": 30},
        "weekdays": [1, 2, 3, 4, 5],
        "active_hours": ["09:00", "18:00"],
        "message": "测试消息",
        "audio": "sounds/bell1.mp3",
        "audio_volume": 0.5,
        "fade_in": False,
        "snooze_enabled": True,
        "max_duration": 0,
        "repeat_count": 1,
    }


@pytest.fixture
def clean_config(temp_config_path):
    """Start with empty default config."""
    from geekclock.core import config

    config.save_config(config.DEFAULT_CONFIG.copy())
    return temp_config_path
