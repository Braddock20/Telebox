from __future__ import annotations

import hashlib
import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db, get_stats, init_db
from .storage import storage_service
from .telegram_manager import account_manager

# Logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Telegram Storage API...")
    Path("data").mkdir(exist_ok=True)
    Path("sessions").mkdir(exist_ok=True)
    await init_db()
    await account_manager.initialize()
    logger.info("Ready. %d account(s) loaded.", len(account_manager.accounts))
    yield
    # Shutdown
    await account_manager.close()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Telegram Storage API",
    description="Unlimited cloud storage backed by Telegram user accounts (Telethon)",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------- Auth helper ----------
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if settings.api_key and settings.api_key != "change-me":
        if not x_api_key or x_api_key != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
            )


# ---------- Schemas ----------
class FileInfo(BaseModel):
    id: str
    filename: str
    size: int
    mime_type: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


# ---------- Routes ----------
@app.get("/health")
async def health():
    accounts = await account_manager.get_status()
    healthy_count = sum(1 for a in accounts if a["healthy"])
    return {
        "status": "ok" if healthy_count > 0 else "degraded",
        "healthy_accounts": healthy_count,
        "total_accounts": len(accounts),
        "accounts": accounts,
    }


@app.get("/storage/stats")
async def storage_stats(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    return await get_stats(db)


@app.post("/files", response_model=FileInfo, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    if not file.filename:
        raise HTTPException(400, "Filename is required")

    # Compute hash while streaming to temp file
    hasher = hashlib.sha256()
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp_path = Path(tmp.name)

    try:
        async with aiofiles.open(tmp_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                hasher.update(chunk)
                await out.write(chunk)

        content_hash = hasher.hexdigest()
        size = tmp_path.stat().st_size

        if size == 0:
            raise HTTPException(400, "Empty file")

        with open(tmp_path, "rb") as f:
            record = await storage_service.upload(
                session=db,
                file_obj=f,
                filename=file.filename,
                content_type=file.content_type,
                content_hash=content_hash,
            )

        return record.to_public_dict()

    except ValueError as e:
        raise HTTPException(413, str(e))
    except Exception as e:
        logger.exception("Upload failed")
        raise HTTPException(500, f"Upload failed: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/files/{file_id}", response_model=FileInfo)
async def get_file_info(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    info = await storage_service.get_info(db, file_id)
    if not info:
        raise HTTPException(404, "File not found")
    return info


@app.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        path = await storage_service.download(db, file_id, tmp_path)
        info = await storage_service.get_info(db, file_id)
        filename = info["filename"] if info else "download"

        return FileResponse(
            path=path,
            filename=filename,
            media_type=info.get("mime_type") if info else "application/octet-stream",
            background=None,  # we clean up ourselves after response
        )
    except FileNotFoundError:
        raise HTTPException(404, "File not found")
    except Exception as e:
        logger.exception("Download failed")
        raise HTTPException(500, f"Download failed: {e}")
    finally:
        # Note: FileResponse will read the file; for production you may want
        # a BackgroundTask to delete after send. For simplicity we leave the
        # temp file (OS will clean /tmp). Improve later if needed.
        pass


@app.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    ok = await storage_service.delete(db, file_id)
    if not ok:
        raise HTTPException(404, "File not found")
    return {"status": "deleted", "id": file_id}


@app.get("/")
async def root():
    return {
        "service": "Telegram Storage API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
