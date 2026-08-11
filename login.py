#!/usr/bin/env python3
"""
One-time login script for Telegram accounts.

Usage:
    python login.py account1
    python login.py account2

It reads the corresponding TELEGRAM_ACCOUNT_N_* values from .env
and creates the .session file.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()


def find_account(name: str) -> dict | None:
    """Find account config by name from environment variables."""
    i = 1
    while True:
        prefix = f"TELEGRAM_ACCOUNT_{i}_"
        acc_name = os.getenv(f"{prefix}NAME")
        if not acc_name:
            break
        if acc_name == name:
            return {
                "name": acc_name,
                "api_id": int(os.getenv(f"{prefix}API_ID")),
                "api_hash": os.getenv(f"{prefix}API_HASH"),
                "session": os.getenv(f"{prefix}SESSION"),
                "channel_id": os.getenv(f"{prefix}CHANNEL_ID"),
            }
        i += 1
    return None


async def main(account_name: str):
    conf = find_account(account_name)
    if not conf:
        print(f"❌ Account '{account_name}' not found in .env")
        print("Available accounts are defined as TELEGRAM_ACCOUNT_N_NAME=...")
        sys.exit(1)

    session_path = Path(conf["session"])
    session_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"→ Logging in as {conf['name']}")
    print(f"  Session file: {session_path}")
    print(f"  Channel ID:   {conf['channel_id']}")
    print()

    client = TelegramClient(
        conf["session"],
        conf["api_id"],
        conf["api_hash"],
    )

    await client.start()  # will prompt for phone + code + 2FA if needed

    me = await client.get_me()
    print()
    print(f"✅ Successfully logged in as: {me.first_name} (@{me.username or 'no-username'})")
    print(f"   User ID: {me.id}")
    print()
    print("You can now start the API server.")
    await client.disconnect()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python login.py <account_name>")
        print("Example: python login.py acc1")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
