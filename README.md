# Telegram Media Ingestion Bot (v1.0 Final)

Production-ready admin-only Telegram media ingestion bot for home media servers (Jellyfin, Plex).

- **python-telegram-bot** (v20+ async)
- **Telethon** (MTProto client for large file downloads >2GB/4GB)
- **MongoDB + Motor** (persistence for users, wizard sessions, and uploads)
- **FFprobe / FFmpeg** (container detection and metadata inspection)
- **Docker Compose**

---

## Features (v1.0 Final)

- **Admin-Only Guard**: Restricts commands and file downloads strictly to `ADMIN_USER_ID`.
- **Zero-Click TV Show Ingestion**: Drop show files directly into the bot; show titles, seasons, and episodes are parsed automatically (e.g. `House.of.the.Dragon.S02E02...` -> `House of the Dragon/Season 02/s02e02.mkv`).
- **Multi-Episode Support**: Handles multi-episode files (e.g. `Friends.S10E17.E18...` -> `s10e17-e18.mkv`), records each episode in MongoDB, and advances the episode counter.
- **Truncated Extension Recovery**: Auto-detects container format via `ffprobe` when Telegram cuts off filenames (e.g. `.10`, `.HEV`, `.[@S`, `.H`, `.WEB-`), ensuring files always save with valid extensions (`.mkv`, `.mp4`).
- **Movie Ingestion**: Direct naming without false positives from leftover encoder/ripper tags.
- **Media Server Auto-Scan (Jellyfin & Plex)**: Silently triggers library refresh in the background (`POST /Library/Refresh` on Jellyfin, `GET /library/sections/all/refresh` on Plex) immediately after file moving.
- **Duplicate Protection**: Warns if a file already exists with overwrite confirmation.
- **Media Browser & Deletion**: Interactive `/delete` hierarchy to browse and remove ingested media directly from Telegram.

---

## Directory Layout

- `/media/jellyfinData/movies` (Movies root directory)
- `/media/jellyfinData/shows` (TV Shows root directory)
- `./data` (Telethon session persistence)
- `./logs` (Application logs)

---

## Quick Start

1. Clone project:
   ```bash
   git clone <repo>
   cd telDownloader
   ```
2. Copy environment template:
   ```bash
   cp .env.example .env
   ```
3. Configure `.env`:
   - `BOT_TOKEN`: Telegram bot token from @BotFather
   - `API_ID` & `API_HASH`: Telegram API credentials from my.telegram.org
   - `ADMIN_USER_ID`: Numeric Telegram user ID
   - `JELLYFIN_URL` & `JELLYFIN_API_KEY`: *(Optional)* Jellyfin auto-scan credentials
   - `PLEX_URL` & `PLEX_TOKEN`: *(Optional)* Plex auto-scan credentials

4. Create Telethon MTProto session **once**:
   ```bash
   docker compose run --rm bot python create_session.py
   ```

5. Start services:
   ```bash
   docker compose up -d --build
   ```

6. Follow logs:
   ```bash
   docker compose logs -f bot
   ```

---

## Bot Commands

- `/start` - Start menu & manual mode picker (Movies / Shows)
- `/status` - Current active session info & download stats
- `/cancel` - Abort active session
- `/stop` - Finish TV show upload batch
- `/delete` - Interactive media browser & deletion tool
- `/help` - Command list
