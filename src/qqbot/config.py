import json
import os
from dataclasses import dataclass
from atri import DATA_DIR


@dataclass
class QQBotConfig:
    app_id: str
    client_secret: str

    def is_configured(self) -> bool:
        return bool(self.app_id and self.client_secret)

    @classmethod
    def load(cls) -> "QQBotConfig":
        config_path = DATA_DIR / "UserSettings.json"
        file_cfg = {}
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                file_cfg = data.get("QQBot", {})
            except (json.JSONDecodeError, OSError):
                pass
        return cls(
            app_id=file_cfg.get("AppId", "") or os.getenv("QQ_APP_ID", ""),
            client_secret=file_cfg.get("ClientSecret", "") or os.getenv("QQ_CLIENT_SECRET", ""),
        )
