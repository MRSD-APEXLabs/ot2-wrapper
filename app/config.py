from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ot2_host: str = "localhost"
    ot2_port: int = 31950
    ot2_traversal_height: float = 120.0
    deck_config_path: Optional[Path] = None

    model_config = {"env_prefix": "", "env_file": ".env"}


settings = Settings()
