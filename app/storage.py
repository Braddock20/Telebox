from __future__ import annotations

import hashlib
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import BinaryIO, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.types import DocumentAttributeFilename

from .config import settings
from .database import FileRecord, get_file_by_id
from .telegram_manager import account_manager

logger = logging.getLogger("storage")


class StorageService:
    """
    High-level storage layer.
    Application code only talks to this class – never to Telegram directly.
    """

    async def upload(
        self,
        session: AsyncSession,
        file_obj: BinaryIO,
        filename: str,
        content_type: Optional[str] = None,
        content_hash: Optional[str] = None,
    ) -> FileRecord:
        # Soft size check
        file_obj.seek(0, 2)
        size = file_obj.tell()
        file_obj.seek(0)

        if size > settings.max_file_size_bytes:
            raise ValueError(
                f"File too large ({size} bytes). Max allowed: {settings.max_file_size_bytes}"
            )

        if not content_type:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # Optional duplicate detection by hash
        if content_hash:
            from sqlalchemy import select
            existing = await session.execute(
                select(FileRecord).where(
                    FileRecord.content_hash == content_hash,
                    FileRecord.is_deleted == False,
                )
            )
            existing_rec = existing.scalar_one_or_none()
            if existing_rec:
                logger.info("Duplicate detected by hash, returning existing file %s", existing_rec.id)
                return existing_rec

        last_error = None
        for attempt in range(1, settings.max_retries + 1):
            account = await account_manager.select_account()
            logger.info(
                "Upload attempt %d/%d using account %s for %s",
                attempt,
                settings.max_retries,
                account.name,
                filename,
            )

            try:
                client = account.client
                # Telethon accepts file-like objects
                message = await client.send_file(
                    entity=account.config.channel_id,
                    file=file_obj,
                    caption=filename,
                    force_document=True,
                    attributes=[DocumentAttributeFilename(filename)],
                    progress_callback=None,  # can be extended later
                )

                if not message or not message.document:
                    raise RuntimeError("Telegram returned no document")

                file_id = str(uuid.uuid4())
                record = FileRecord(
                    id=file_id,
                    filename=filename,
                    original_filename=filename,
                    size=message.document.size,
                    mime_type=content_type,
                    content_hash=content_hash,
                    account_name=account.name,
                    channel_id=account.config.channel_id,
                    message_id=message.id,
                    file_id=message.document.id,
                    access_hash=message.document.access_hash,
                )
                session.add(record)
                await session.flush()

                await account_manager.mark_success(account.name)
                logger.info("Uploaded %s → file_id=%s (msg %s)", filename, file_id, message.id)
                return record

            except FloodWaitError as e:
                wait = e.seconds
                logger.warning("FloodWait on %s: sleeping %s seconds", account.name, wait)
                await account_manager.mark_failure(account.name, f"FloodWait {wait}s")
                await asyncio.sleep(min(wait, 60))
                last_error = e
                # reset file pointer for retry
                file_obj.seek(0)

            except (RPCError, Exception) as e:
                logger.exception("Upload failed on account %s", account.name)
                await account_manager.mark_failure(account.name, str(e))
                last_error = e
                file_obj.seek(0)

        raise RuntimeError(f"Upload failed after {settings.max_retries} attempts: {last_error}")

    async def download(
        self,
        session: AsyncSession,
        file_id: str,
        destination: Path | str,
    ) -> Path:
        record = await get_file_by_id(session, file_id)
        if not record:
            raise FileNotFoundError(f"File {file_id} not found")

        account = account_manager.accounts.get(record.account_name)
        if not account or not account.is_healthy:
            # Try to reconnect or fall back? For now raise
            raise RuntimeError(f"Account {record.account_name} is not available")

        client = account.client
        message = await client.get_messages(record.channel_id, ids=record.message_id)
        if not message or not message.document:
            raise FileNotFoundError("Message or document no longer exists on Telegram")

        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)

        path = await message.download_media(file=str(dest))
        return Path(path)

    async def delete(self, session: AsyncSession, file_id: str) -> bool:
        """Soft-delete in our DB. Optionally delete the Telegram message."""
        record = await get_file_by_id(session, file_id)
        if not record:
            return False

        # Soft delete
        record.is_deleted = True
        await session.flush()

        # Best-effort hard delete on Telegram
        try:
            account = account_manager.accounts.get(record.account_name)
            if account and account.client:
                await account.client.delete_messages(
                    record.channel_id, [record.message_id]
                )
        except Exception as e:
            logger.warning("Could not delete Telegram message for %s: %s", file_id, e)

        return True

    async def get_info(self, session: AsyncSession, file_id: str) -> Optional[dict]:
        record = await get_file_by_id(session, file_id)
        if not record:
            return None
        return record.to_public_dict()


# Import asyncio here to avoid circular issues in some environments
import asyncio

storage_service = StorageService()
