from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.types import DocumentAttributeFilename

from .config import settings, TelegramAccountConfig

logger = logging.getLogger("telegram_manager")


@dataclass
class AccountState:
    config: TelegramAccountConfig
    client: Optional[TelegramClient] = None
    is_healthy: bool = True
    last_error: Optional[str] = None
    last_used: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    upload_count: int = 0
    fail_count: int = 0
    consecutive_fails: int = 0

    @property
    def name(self) -> str:
        return self.config.name


class AccountManager:
    """
    Manages multiple Telegram user accounts.
    Handles connection pooling, health tracking, and intelligent selection.
    """

    def __init__(self):
        self.accounts: Dict[str, AccountState] = {}
        self._lock = asyncio.Lock()
        self._round_robin_idx = 0

    async def initialize(self) -> None:
        if not settings.accounts:
            raise RuntimeError(
                "No Telegram accounts configured. "
                "Please set TELEGRAM_ACCOUNT_1_* variables in .env"
            )

        for conf in settings.accounts:
            state = AccountState(config=conf)
            # Ensure session directory exists
            session_path = Path(conf.session)
            session_path.parent.mkdir(parents=True, exist_ok=True)

            client = TelegramClient(
                conf.session,
                conf.api_id,
                conf.api_hash,
                connection_retries=3,
                retry_delay=2,
                auto_reconnect=True,
            )
            state.client = client
            self.accounts[conf.name] = state
            logger.info("Registered account: %s (channel %s)", conf.name, conf.channel_id)

        # Connect all accounts
        await asyncio.gather(*(self._connect(name) for name in self.accounts))

    async def _connect(self, name: str) -> None:
        state = self.accounts[name]
        try:
            await state.client.connect()
            if not await state.client.is_user_authorized():
                state.is_healthy = False
                state.last_error = "Session not authorized. Run the login script first."
                logger.error("Account %s is not authorized", name)
            else:
                me = await state.client.get_me()
                state.is_healthy = True
                state.last_error = None
                logger.info("Account %s connected as %s", name, me.username or me.id)
        except Exception as e:
            state.is_healthy = False
            state.last_error = str(e)
            logger.exception("Failed to connect account %s", name)

    async def close(self) -> None:
        for state in self.accounts.values():
            if state.client and state.client.is_connected():
                await state.client.disconnect()

    def get_healthy_accounts(self) -> List[AccountState]:
        return [a for a in self.accounts.values() if a.is_healthy]

    async def select_account(self) -> AccountState:
        """Select an account according to UPLOAD_STRATEGY."""
        healthy = self.get_healthy_accounts()
        if not healthy:
            raise RuntimeError("No healthy Telegram accounts available")

        strategy = settings.upload_strategy.lower()

        if strategy == "least_used":
            return min(healthy, key=lambda a: a.upload_count)

        if strategy == "random":
            return random.choice(healthy)

        # Default: round_robin
        async with self._lock:
            self._round_robin_idx = (self._round_robin_idx + 1) % len(healthy)
            return healthy[self._round_robin_idx]

    async def mark_success(self, name: str) -> None:
        state = self.accounts.get(name)
        if state:
            state.upload_count += 1
            state.consecutive_fails = 0
            state.last_used = datetime.now(timezone.utc)
            state.is_healthy = True
            state.last_error = None

    async def mark_failure(self, name: str, error: str) -> None:
        state = self.accounts.get(name)
        if not state:
            return
        state.fail_count += 1
        state.consecutive_fails += 1
        state.last_error = error
        state.last_used = datetime.now(timezone.utc)

        # Temporary mark unhealthy after several consecutive failures
        if state.consecutive_fails >= 5:
            state.is_healthy = False
            logger.warning(
                "Account %s marked unhealthy after %d consecutive failures: %s",
                name,
                state.consecutive_fails,
                error,
            )

    async def get_status(self) -> List[dict]:
        result = []
        for name, state in self.accounts.items():
            result.append(
                {
                    "name": name,
                    "healthy": state.is_healthy,
                    "upload_count": state.upload_count,
                    "fail_count": state.fail_count,
                    "consecutive_fails": state.consecutive_fails,
                    "last_error": state.last_error,
                    "last_used": state.last_used.isoformat() if state.last_used else None,
                    "channel_id": state.config.channel_id,
                }
            )
        return result


# Global instance
account_manager = AccountManager()
