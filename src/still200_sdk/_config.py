"""SDK configuration."""

import os
from dataclasses import dataclass, field
from typing import Self

DEFAULT_BASE_URL = "https://api.still200.com"
DEFAULT_TIMEOUT = 5.0
PING_TOKEN_ENV_VAR = "STILL200_PING_TOKEN"


@dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    """Internal configuration for Still200 API requests."""

    ping_token: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT

    def __post_init__(self) -> None:
        ping_token = self.ping_token.strip()
        base_url = self.base_url.rstrip("/")

        if not ping_token:
            raise ValueError("ping_token must not be empty")
        if not base_url:
            raise ValueError("base_url must not be empty")
        if self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        object.__setattr__(self, "ping_token", ping_token)
        object.__setattr__(self, "base_url", base_url)

    @classmethod
    def from_env(cls) -> Self:
        """Load configuration from the process environment."""
        ping_token = os.getenv(PING_TOKEN_ENV_VAR)

        if ping_token is None:
            raise ValueError(f"{PING_TOKEN_ENV_VAR} is not set")

        return cls(ping_token=ping_token)
