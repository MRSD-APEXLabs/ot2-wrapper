import os
from pathlib import Path

import yaml

_CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.yaml"))


def _load() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


class Settings:
    def __init__(self) -> None:
        data = _load()
        robot = data.get("robot", {})
        self.ot2_host: str = robot.get("host", "localhost")
        self.ot2_port: int = int(robot.get("port", 31950))
        self.ot2_traversal_height: float = float(robot.get("traversal_height", 120.0))
        self.deck_config_path: Path | None = _CONFIG_PATH if _CONFIG_PATH.exists() else None


settings = Settings()
