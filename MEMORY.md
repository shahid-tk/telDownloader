# Repository Memory & Knowledge Base

## System Architecture & Data Model

### MongoDB Collections (`media_ingestion`)

1. **`users`**:
   - `telegram_id` (int, unique index): Admin ID
   - `role` (str): `"admin"`
   - `created_at` (datetime)

2. **`sessions`**:
   - `chat_id` (int, unique index): Telegram Chat ID
   - `mode` (str): `"movie"` | `"show"`
   - `movie_name` (str, optional)
   - `show_name` (str, optional)
   - `season` (int, optional)
   - `next_episode` (int, default 1)
   - `episodes_uploaded` (int, default 0)
   - `updated_at` (datetime)

3. **`uploads`**:
   - `media_type` (str): `"movie"` | `"show"`
   - `title` (str)
   - `season` (int, optional)
   - `episode` (int, optional)
   - `file_path` (str): Target path on disk
   - `file_size` (int): In bytes
   - `video_codec`, `audio_codec`, `resolution`, `duration`: Metadata from `ffprobe`
   - `uploaded_at` (datetime)

---

## Critical Component Details & Gotchas

### 1. Telethon User Session (`services/telethon_service.py`)
- Standard bot tokens have Telegram file download limits (20MB/50MB). To support multi-gigabyte media files (>2GB / 4GB), Telethon runs a MTProto user session via `app/data/telethon.session`.
- Session creation is interactive and executed once via `docker compose run --rm bot python create_session.py`.
- If `TELETHON_SOURCE_CHAT` is configured, Telethon searches that chat for message IDs; otherwise, it handles direct messages/forwards.

### 2. FFprobe Stream Inspection (`utils/ffprobe.py`)
- Executed on media before final storage moving.
- Extracts Video (codec, resolution, fps), Audio (codec, channels, language), and Subtitles (codecs, languages).
- Formats inline summary with continuation buttons (`meta_continue`, `meta_cancel`).

### 3. Media Path Conventions (`app/config.py`, `services/media_service.py`)
- Movies mount: `MOVIES_DIR` (default `/mnt/movies_share`) -> `/{Movie (Year)}/{Movie (Year)}.{ext}`
- Shows mount: `SHOWS_DIR` (default `/mnt/shows_share`) -> `/{Show Name}/Season {XX}/{Show Name} - S{XX}E{YY}.{ext}`
- Temporary download staging: `/tmp` or internal buffer before moving to destination share.

### 4. Progress Throttling & Telegram Rate Limits (`services/download_service.py`)
- Progress callback uses elapsed time calculation to only update Telegram status message if `current_time - last_update >= 5.0` seconds to avoid `429 Too Many Requests / FloodWait`.

### 5. Deletion Engine (`handlers/delete_callbacks.py`)
- Deep deletion hierarchy: Browse Movies vs Shows -> Select Show -> Select Season -> Select Episode -> Confirm.
- Deletion removes the physical file from `/mnt/...` and deletes the matching record in the `uploads` collection. If a season/show folder is empty after deletion, the empty directory is cleaned up.

### 6. Git Exclusion & Data Persistence Policies (`.gitignore`)
- **Secrets & Credentials**: `.env`, `.env.*` are strictly ignored; `.env.example` is committed as a template.
- **MTProto Sessions**: `data/` directory and `*.session` files contain active Telethon login credentials and are excluded from version control.
- **Database & Logs**: MongoDB storage (`mongo_data/`, `*.db`) and application log files (`logs/`, `*.log*`) are persisted on disk/volumes but ignored in Git.
- **Python / Virtual Environments**: `__pycache__/`, `*.pyc`, `venv/`, `.venv/` are excluded.

---

## Environment Variables Reference
| Variable | Description | Default |
|---|---|---|
| `BOT_TOKEN` | Telegram Bot Token from @BotFather | *(Required)* |
| `ADMIN_USER_ID` | Numeric Telegram ID of authorized administrator | *(Required)* |
| `API_ID` | Telegram API ID from my.telegram.org | *(Required)* |
| `API_HASH` | Telegram API Hash from my.telegram.org | *(Required)* |
| `SESSION_FILE` | Telethon `.session` file path | `/app/data/telethon.session` |
| `MONGO_URI` | MongoDB connection URI | `mongodb://mongodb:27017/media_ingestion` |
| `MOVIES_DIR` | Movies storage root directory | `/mnt/movies_share` |
| `SHOWS_DIR` | TV shows storage root directory | `/mnt/shows_share` |
| `TELETHON_SOURCE_CHAT` | Optional source chat ID / username | `""` |
| `LOG_FILE` | Application log file path | `/app/logs/app.log` |
| `LOG_LEVEL` | Log severity level | `INFO` |
