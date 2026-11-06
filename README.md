# Telegram Media Ingestion Bot (`telDownloader`)

A modern, high-performance, admin-only media ingestion system designed for home media servers (Jellyfin, Plex). It automatically downloads, parses, standardizes, and organizes movies and TV shows from Telegram directly into your media library with real-time web monitoring and management.

---

## ✨ Features

### 📥 Media Ingestion & Parsing
- **Zero-Click TV Show Ingestion**: Drop show files directly into the bot; show titles, seasons, and episodes are parsed automatically (e.g. `House.of.the.Dragon.S02E02...` ➔ `House of the Dragon/Season 02/s02e02.mkv`).
- **Multi-Episode Handling**: Automatically detects multi-episode files (e.g. `Friends.S10E17.E18...` ➔ `s10e17-e18.mkv`) and properly updates episode indexes.
- **Truncated Extension Recovery**: Auto-detects container formats via `ffprobe` when Telegram truncates filenames (e.g. `.10`, `.HEV`, `.[@S`, `.H`, `.WEB-`), ensuring files are always saved with correct extensions (`.mkv`, `.mp4`).
- **Telethon MTProto Acceleration**: Downloads files of any size (including files >2GB / >4GB) using Telegram MTProto user sessions.
- **Media Server Auto-Scan**: Triggers library refreshes immediately on Jellyfin (`POST /Library/Refresh`) and Plex (`GET /library/sections/all/refresh`) after files are saved.
- **Duplicate & Overwrite Guard**: Detects existing files and requests confirmation before overwriting.

### 🌐 Integrated Web Dashboard (Port `8088`)
- **Live Download Tracker**: Real-time WebSocket monitor (`/ws/downloads`) showing active download speed, ETA, progress bars, downloaded/total bytes, and status.
- **Library Manager**: Browse and manage your ingested Movies and TV Shows directly from the browser with safe deletion confirmation.
- **Web-Based Configuration**: Update credentials, media folder paths, and log levels directly from the web interface without touching the terminal.
- **Sensitive Credential Protection**: Inputs for Telegram Bot Token, Admin User ID, API ID, API Hash, and passwords are masked by default with convenient show/hide eye toggles (`👁️` / `🙈`).
- **Form-Based Session Authentication**: Protected by secure HTTP-only session cookies (`tel_session`) with dedicated login (`/login`) and logout (`/logout`) endpoints.
- **Zero-Friction Out-of-the-Box Access**: Ships by default with `WEB_USERNAME=admin` and no password. Enter your desired password in the Configuration tab whenever you are ready to secure it.

### 🤖 Telegram Bot Control & Emergency Recovery
- Full control via Telegram bot commands.
- **Self-Service Password Reset**: If you ever forget your web password, reset or change it instantly directly from your Telegram admin chat (`/resetweb` or `/webpass <pwd>`).

---

## 🏗️ Architecture

```
                       ┌───────────────────────────────┐
                       │     Telegram Bot (MTProto)    │
                       │    python-telegram-bot v20+   │
                       └──────────────┬────────────────┘
                                      │
┌──────────────────────────────┐      │      ┌───────────────────────────────┐
│     FastAPI Web Dashboard    │◄─────┴─────►│       Ingestion Pipeline      │
│     Uvicorn (Port 8088)      │             │  Telethon + SQLite + FFmpeg   │
└──────────────────────────────┘             └──────────────┬────────────────┘
                                                            │
                                             ┌──────────────┴────────────────┐
                                             ▼                               ▼
                                  ┌─────────────────────┐        ┌─────────────────────┐
                                  │   Jellyfin Server   │        │     Plex Server     │
                                  └─────────────────────┘        └─────────────────────┘
```

- **Single Container**: Runs both the Telegram Bot and FastAPI Web Server concurrently in a single lightweight Docker container (`python:3.12-slim`).
- **Embedded SQLite**: Zero-maintenance local database stored at `/app/data/media_data.db` (no external database containers needed).

---

## 🚀 Quick Start

### 1. Clone & Setup
```bash
git clone <repo-url> telDownloader
cd telDownloader
cp .env.example .env
```

### 2. Configure Environment (`.env`)
Edit `.env` with your core credentials:
```env
# Telegram Bot & Admin
BOT_TOKEN=123456789:ABCDefghIJKLmnopQRSTuvwxYZ
ADMIN_USER_ID=123456789

# Telethon MTProto API Credentials (from https://my.telegram.org)
API_ID=12345678
API_HASH=0123456789abcdef0123456789abcdef

# Media Directories (Paths on host)
MOVIES_DIR=./media/movies
SHOWS_DIR=./media/shows

# Web Interface
WEB_PORT=8088
WEB_USERNAME=admin
WEB_PASSWORD=

# Optional Media Server Webhooks
JELLYFIN_URL=http://jellyfin:8096
JELLYFIN_API_KEY=
PLEX_URL=http://plex:32400
PLEX_TOKEN=
```

### 3. Generate Telethon Session (One-Time Setup)
Create your MTProto user session file by logging in with your Telegram phone number:
```bash
docker compose run --rm bot python create_session.py
```
*Follow the interactive prompt to enter your phone number and login verification code.*

### 4. Build and Start the Container
```bash
docker compose up -d --build
```

### 5. Access the Web Dashboard
Open your browser and navigate to:
```
http://<server-ip>:8088/
```
- **Username**: `admin`
- **Password**: *(leave blank on first login)*
- Click **Sign In** to access the dashboard.
- To set a password, open the **Configuration** tab, enter a password in **Web Dashboard Password**, and click **Save Configuration**.

---

## 🤖 Bot Commands

| Command | Description |
| :--- | :--- |
| `/start` | Launch interactive menu and select mode (Movies / Shows) |
| `/status` | View current download progress, speed, and session state |
| `/cancel` | Abort the active download or ingestion session |
| `/stop` | Complete the current TV show upload batch |
| `/delete` | Interactive Telegram browser to inspect and delete ingested files |
| `/resetweb` | Reset web dashboard password back to default (blank) |
| `/webpass <pwd>` | Set a new web dashboard password directly from Telegram |
| `/help` | Display list of available commands |

---

## 🔑 Password Recovery

If you ever forget the password to the web dashboard, choose either method:

### Method A: Via Telegram (No SSH Needed)
Send this command to your bot in Telegram:
```text
/resetweb
```
*The bot resets your password immediately and confirms in chat. You can then log in using `admin` with a blank password.*

Or set a new password on the fly:
```text
/webpass MyNewPassword123
```

### Method B: Via Server Terminal (SSH)
Run this one-liner on your host server:
```bash
sed -i 's/^WEB_PASSWORD=.*/WEB_PASSWORD=/' /docker-apps/telDownloader/.env && docker restart telegram_media_ingestion_bot
```

---

## 📁 Directory Structure

```text
telDownloader/
├── app/
│   ├── bot.py                  # Main entry point (Bot + FastAPI runner)
│   ├── config.py               # Pydantic settings & env manager
│   ├── database/
│   │   └── sqlite.py           # Embedded SQLite persistence
│   ├── handlers/               # Telegram bot command handlers
│   │   ├── auth_cmd.py         # /resetweb & /webpass commands
│   │   ├── cancel.py           # /cancel command
│   │   ├── delete.py           # /delete command & browser
│   │   ├── movie.py            # Movie ingestion logic
│   │   ├── show.py             # Show parsing & episode numbering
│   │   ├── start.py            # Interactive menus
│   │   └── status.py           # /status progress reports
│   ├── services/
│   │   ├── download_tracker.py # Real-time download progress tracker
│   │   ├── media_service.py    # File naming & format detection
│   │   ├── media_server.py     # Jellyfin / Plex webhooks
│   │   └── telethon_service.py # Telethon client wrapper
│   └── web/
│       └── server.py           # FastAPI server, UI & WebSockets
├── data/                       # Persistent SQLite DB & Telethon sessions
├── logs/                       # Application logs
├── docker-compose.yml          # Container deployment definition
├── Dockerfile                  # Container build recipe
├── requirements.txt            # Python dependencies
└── .env.example                # Sample environment file
```

---

## 📜 License
MIT License. Created for personal and home-lab media server automation.
