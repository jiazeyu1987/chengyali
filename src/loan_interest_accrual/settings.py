from dataclasses import dataclass
from typing import Final


LOOPBACK_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 8000


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = LOOPBACK_HOST
    port: int = DEFAULT_PORT


DEFAULT_SETTINGS: Final[Settings] = Settings()
