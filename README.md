# Telegram Storage API

Unlimited cloud storage powered by **Telegram user accounts** (Telethon / MTProto).

Your application talks to a clean REST API.  
Telegram is only the backend adapter – you never expose channel IDs or message IDs to clients.

## Features

- Multiple Telegram accounts (add as many as you want via `.env`)
- Configurable upload strategy: `round_robin` | `least_used` | `random`
- Automatic retries + health tracking of accounts
- Soft size limits + SHA-256 duplicate detection
- Own file IDs (UUID) – Telegram details stay internal
- FastAPI + async SQLAlchemy
- Simple API key authentication

## Quick Start

### 1. Clone & install

```bash
cd telegram-storage
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

- Set a strong `API_KEY`
- Fill in your Telegram accounts (`TELEGRAM_ACCOUNT_1_*`, `TELEGRAM_ACCOUNT_2_*`, …)

For each account you need:
- `api_id` + `api_hash` from https://my.telegram.org
- A private channel (create one, then get its ID – it starts with `-100`)

### 3. Login (one-time per account)

```bash
python login.py acc1
python login.py acc2
```

This creates the session files under `sessions/`.

### 4. Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Open http://localhost:8080/docs for the interactive Swagger UI.

## API Endpoints

| Method | Path                    | Description                  |
|--------|-------------------------|------------------------------|
| GET    | `/health`               | Service + account health     |
| GET    | `/storage/stats`        | Storage statistics           |
| POST   | `/files`                | Upload a file                |
| GET    | `/files/{id}`           | Get file metadata            |
| GET    | `/files/{id}/download`  | Download the file            |
| DELETE | `/files/{id}`           | Soft-delete the file         |

All endpoints except `/health` and `/` require the header:

```
X-API-Key: your-api-key
```

### Example upload

```bash
curl -X POST http://localhost:8080/files \
  -H "X-API-Key: your-api-key" \
  -F "file=@movie.mp4"
```

Response:

```json
{
  "id": "01JXYZ...",
  "filename": "movie.mp4",
  "size": 734003200,
  "mime_type": "video/mp4",
  "created_at": "2026-08-11T09:30:00Z",
  "updated_at": "2026-08-11T09:30:00Z"
}
```

## Project Structure

```
telegram-storage/
├── app/
│   ├── main.py              # FastAPI routes
│   ├── storage.py           # High-level storage service
│   ├── telegram_manager.py  # Multi-account manager + health
│   ├── database.py          # SQLAlchemy models
│   └── config.py            # Settings + dynamic account loading
├── sessions/                # Telethon session files (git-ignored)
├── data/                    # SQLite database
├── login.py                 # One-time account login helper
├── .env.example
├── requirements.txt
└── README.md
```

## Adding a new account

Just add three more lines to `.env`:

```env
TELEGRAM_ACCOUNT_3_NAME=acc3
TELEGRAM_ACCOUNT_3_API_ID=...
TELEGRAM_ACCOUNT_3_API_HASH=...
TELEGRAM_ACCOUNT_3_SESSION=sessions/account3
TELEGRAM_ACCOUNT_3_CHANNEL_ID=-100...
```

Then run:

```bash
python login.py acc3
```

Restart the server – no code changes needed.

## Important Notes

- **File size limit**: Telegram free accounts = 2 GB, Premium = 4 GB. The soft limit is controlled by `MAX_FILE_SIZE_MB`.
- **Rate limits**: The service respects `FloodWait` and will temporarily mark unhealthy accounts.
- **Privacy**: Normal Telegram channels are **not** end-to-end encrypted. Encrypt sensitive data before uploading if needed.
- **Account health**: Keep the accounts mildly active so Telegram doesn’t mark them inactive.
- **Backup**: The `.session` files + the SQLite database are critical. Back them up.

## License

MIT – use it however you like.
