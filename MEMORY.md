# Repository Memory & Knowledge Base (v1.0 Final)

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
   - `type` (str): `"movie"` | `"show"`
   - `movie_name` / `show_name` (str)
   - `season` (int, optional)
   - `episode` (int, optional)
   - `filename` (str)
   - `path` (str): Target path on disk
   - `uploaded_at` (datetime)

---

## Critical Component Details

### 1. Telethon User Session (`services/telethon_service.py`)
- Standard bot tokens have Telegram file download limits (20MB/50MB). To support multi-gigabyte media files (>2GB / 4GB), Telethon runs an MTProto user session via `app/data/telethon.session`.
- Bind-mounted to `./data:/app/data`, persisting across container restarts and redeployments.

### 2. Media Server Integration (`services/media_server.py`)
- Background, non-blocking library refresh triggers for **Jellyfin** (`POST /Library/Refresh` with `Authorization: MediaBrowser Token="..."`) and **Plex** (`GET /library/sections/all/refresh` with `X-Plex-Token`).
- Optional; swallows all network exceptions so uploads never fail if media servers are offline or unresponsive. Runs completely silently.

### 3. TV Show Filename & Extension Engine (`utils/helpers.py`, `utils/ffprobe.py`)
- `parse_show_info`: Zero-click parsing of show title, season, and episodes directly from release filenames (cleaning release group tags, preserving release years).
- `extract_season_episodes`: Multi-episode regex parsing (e.g., `S10E17.E18`, `S02E01-E02`).
- `get_video_extension`: Sanitizes truncated Telegram file extensions (`.10`, `.HEV`, `.[@S`, `.H`, `.WEB-`, trailing `.`) using `ffprobe` format detection, defaulting cleanly to `.mkv`.
- `format_season_episode`: Plex/Jellyfin standard format (`s10e17-e18.mkv`, `s02e02.mkv`).

### 4. Media Storage Paths
- Movies mount: `MOVIES_DIR` (`/media/jellyfinData/movies`)
- Shows mount: `SHOWS_DIR` (`/media/jellyfinData/shows`)
- Temporary staging: `.tmp/` inside respective media mount points before moving.

### 5. Git Exclusion & Data Persistence Policies (`.gitignore`)
- Secrets & Credentials: `.env`, `.env.*` are ignored; `.env.example` is committed.
- MTProto Sessions: `data/` and `*.session` are excluded.
- Database & Logs: `mongo_data/` and `logs/` are excluded.
