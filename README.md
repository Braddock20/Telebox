# Telegram Storage v2

A production-oriented REST storage service backed by Telegram user accounts.

### Why v2?

The original Python/Telethon version had several reliability problems (notably retry handling, temporary-file lifecycle, and account failover). v2 moves the Telegram layer to Node/TypeScript and combines **teleproto + GramJS** behind one adapter:

- **teleproto first** — current MTProto implementation and typed raw API surface.
- **GramJS fallback** — battle-tested compatibility path.
- Per-account engine selection: `auto`, `teleproto`, or `gramjs`.
- Automatic account failover and FloodWait-aware backoff.
- StringSession in `.env` — easy deployment and no session files required.
- Atomic metadata writes in SQLite.
- SHA-256 deduplication.
- Streaming multipart upload to disk before Telegram transfer.
- Download cleanup with Fastify lifecycle.
- Health and storage statistics.
- Built-in smoke tests that do not require Telegram credentials.

teleproto is a 2025 fork of GramJS with a GramJS-compatible public surface, so this architecture intentionally keeps both behind the same adapter rather than mixing two clients on one live session. citeturn0search0turn0search3

## Setup

```bash
npm install
cp .env.example .env
npm run typecheck
npm test
npm run build
```

Then configure `.env`.

## Login

For each account:

```bash
npm run login -- acc1
```

The script asks for phone/code/2FA and prints a `StringSession`. Paste it into:

```env
TELEGRAM_ACCOUNT_1_SESSION=...
```

A Telegram `api_id` and `api_hash` are required. Both teleproto and GramJS use MTProto user sessions rather than the Bot API. citeturn0search1turn1search1

## Channel

Create a private channel for storage and add each storage account as an administrator. Put its numeric `-100...` channel ID in the corresponding account variable.

## Run

```bash
npm run dev
# or
npm run build && npm start
```

Interactive API docs are at `/docs` when running.

## API

- `GET /health` — service/account/engine health.
- `GET /storage/stats` — metadata statistics.
- `POST /files` — multipart upload (`file` field).
- `GET /files/:id` — metadata.
- `GET /files/:id/download` — download.
- `DELETE /files/:id` — delete metadata and Telegram message.

All routes except `/` and `/health` require `X-API-Key`.

### Example

```bash
curl -X POST http://localhost:8080/files \
  -H 'X-API-Key: YOUR_KEY' \
  -F 'file=@movie.mp4'
```

### Important

Telegram storage is not a magic unlimited disk. Account limits, flood limits, channel permissions, network throughput and Telegram policy still apply. This service only manages the storage layer; it does not bypass Telegram limits.

Never commit `.env` or session strings.
