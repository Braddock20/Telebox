from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramAccountConfig(BaseSettings):
    name: str
    api_id: int
    api_hash: str
    session: str
    channel_id: int

    model_config = SettingsConfigDict(extra="ignore")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    api_key: str = "change-me"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/storage.db"

    # Behaviour
    upload_strategy: str = "round_robin"  # round_robin | least_used | random
    max_retries: int = 3
    upload_timeout: int = 300
    download_timeout: int = 300
    max_file_size_mb: int = 2000

    # Dynamically loaded accounts
    accounts: List[TelegramAccountConfig] = Field(default_factory=list)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_accounts_from_env()

    def _load_accounts_from_env(self) -> None:
        """Parse TELEGRAM_ACCOUNT_{N}_* variables from environment."""
        env = os.environ
        # Find all account indices
        indices = set()
        pattern = re.compile(r"^TELEGRAM_ACCOUNT_(\d+)_NAME$", re.IGNORECASE)
        for key in env:
            match = pattern.match(key)
            if match:
                indices.add(int(match.group(1)))

        accounts: List[TelegramAccountConfig] = []
        for idx in sorted(indices):
            prefix = f"TELEGRAM_ACCOUNT_{idx}_"
            name = env.get(f"{prefix}NAME")
            api_id = env.get(f"{prefix}API_ID")
            api_hash = env.get(f"{prefix}API_HASH")
            session = env.get(f"{prefix}SESSION")
            channel_id = env.get(f"{prefix}CHANNEL_ID")

            if not all([name, api_id, api_hash, session, channel_id]):
                continue

            accounts.append(
                TelegramAccountConfig(
                    name=name,
                    api_id=int(api_id),
                    api_hash=api_hash,
                    session=session,
                    channel_id=int(channel_id),
                )
            )

        self.accounts = accounts

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


# Global settings instance (loaded once)
settings = Settings()
