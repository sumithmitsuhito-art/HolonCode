import json
import pytest
from pathlib import Path
from atri import DATA_DIR


@pytest.fixture
def clean_settings():
    settings_path = DATA_DIR / "UserSettings.json"
    backup = None
    if settings_path.exists():
        backup = settings_path.read_bytes()
    yield
    if backup is not None:
        settings_path.write_bytes(backup)
    elif settings_path.exists():
        settings_path.unlink()


def test_load_empty_config(clean_settings):
    from qqbot.config import QQBotConfig
    settings_path = DATA_DIR / "UserSettings.json"
    if settings_path.exists():
        settings_path.unlink()
    cfg = QQBotConfig.load()
    assert cfg.app_id == ""
    assert cfg.client_secret == ""


def test_load_from_file(clean_settings):
    from qqbot.config import QQBotConfig
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "UserSettings.json").write_text(json.dumps({
        "QQBot": {"AppId": "test-app-id", "ClientSecret": "test-secret"}
    }), encoding="utf-8")
    cfg = QQBotConfig.load()
    assert cfg.app_id == "test-app-id"
    assert cfg.client_secret == "test-secret"


def test_load_from_env(clean_settings, monkeypatch):
    from qqbot.config import QQBotConfig
    settings_path = DATA_DIR / "UserSettings.json"
    if settings_path.exists():
        settings_path.unlink()
    monkeypatch.setenv("QQ_APP_ID", "env-app-id")
    monkeypatch.setenv("QQ_CLIENT_SECRET", "env-secret")
    cfg = QQBotConfig.load()
    assert cfg.app_id == "env-app-id"
    assert cfg.client_secret == "env-secret"


def test_is_configured():
    from qqbot.config import QQBotConfig
    assert not QQBotConfig("", "").is_configured()
    assert QQBotConfig("id", "secret").is_configured()
