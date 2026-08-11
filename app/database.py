from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import settings


class Base(DeclarativeBase):
    pass


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    filename: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # sha256

    # Telegram internal (never exposed to clients)
    account_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Telegram document id
    access_hash: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "size": self.size,
            "mime_type": self.mime_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Engine & session
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_file_by_id(session: AsyncSession, file_id: str) -> Optional[FileRecord]:
    result = await session.execute(
        select(FileRecord).where(FileRecord.id == file_id, FileRecord.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_stats(session: AsyncSession) -> dict:
    total = await session.scalar(
        select(func.count()).select_from(FileRecord).where(FileRecord.is_deleted == False)
    )
    total_size = await session.scalar(
        select(func.coalesce(func.sum(FileRecord.size), 0)).where(FileRecord.is_deleted == False)
    )
    by_account = await session.execute(
        select(FileRecord.account_name, func.count(), func.coalesce(func.sum(FileRecord.size), 0))
        .where(FileRecord.is_deleted == False)
        .group_by(FileRecord.account_name)
    )
    accounts = [
        {"account": row[0], "files": row[1], "total_size": row[2]}
        for row in by_account.all()
    ]
    return {
        "total_files": total or 0,
        "total_size_bytes": total_size or 0,
        "by_account": accounts,
    }
