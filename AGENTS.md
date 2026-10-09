# Agent Guidelines & Repository Context

## Project Overview
**telDownloader** is an admin-only Telegram media ingestion bot designed for home media servers (Plex, Jellyfin).
- **Core Stack**: Python 3.11+, `python-telegram-bot` (v20+ async), `Telethon` (MTProto client for large file downloads >2GB), `Motor`/`MongoDB` (session & upload persistence), `ffmpeg`/`ffprobe` (media stream inspection), Docker Compose.
- **Goal**: Ingest movies and TV shows from Telegram directly into structured media directories (`/mnt/movies_share`, `/mnt/shows_share`).

---

## Directory Structure & Key Files
```
├── app/
│   ├── bot.py                     # Main application entry point, lifecycle & handler registration
│   ├── config.py                  # Pydantic Settings (.env configuration)
│   ├── create_session.py          # One-time interactive script to generate Telethon session string
│   ├── requirements.txt           # Python dependencies
│   ├── database/
│   │   ├── mongo.py               # Motor client wrapper and index definitions
│   │   └── repositories/
│   │       ├── users_repo.py      # Admin user initialization & checks
│   │       ├── sessions_repo.py   # State tracking for active wizard workflows
│   │       └── uploads_repo.py    # Log of downloaded files (movie & show episodes)
│   ├── handlers/
│   │   ├── start.py               # /start command & menu initialization
│   │   ├── movie.py               # Movie naming & setup prompt
│   │   ├── show.py                # TV Show naming & season setup prompt
│   │   ├── status.py              # /status command (current session & stats)
│   │   ├── cancel.py              # /cancel command (abort current session)
│   │   ├── delete.py              # /delete command entry point
│   │   ├── delete_callbacks.py    # Interactive media browser & deletion handlers
│   │   └── callbacks.py           # Inline button routers (modes, resume/discard, overwrite)
│   ├── services/
│   │   ├── download_service.py    # Telethon download coordinator with progress throttler
│   │   ├── media_service.py       # Core orchestration (ingestion, naming, validation, moving)
│   │   ├── session_service.py     # MongoDB session cache & state manager
│   │   └── telethon_service.py    # Telethon client lifecycle manager
│   └── utils/
│       ├── auth.py                # Admin authorization guard (ADMIN_USER_ID)
│       ├── ffprobe.py             # FFprobe stream analyzer (audio/video/subs codecs)
│       ├── helpers.py             # Filename sanitization, formatting, directory helpers
│       └── logger.py              # Standardized logging setup
├── data/                          # Telethon session file storage (persisted, gitignored)
├── logs/                          # Log file storage (app.log, gitignored)
├── .gitignore                     # Git ignore rules (env, sessions, mongo, logs, cache)
├── docker-compose.yml             # Bot & MongoDB container configuration
├── Dockerfile                     # Base python image with ffmpeg installed
└── .env.example                   # Environment configuration template
```

---

## Core Operational Workflows

1. **Authentication**:
   - Every command and callback queries `utils.auth.guard_admin()`.
   - Access is restricted exclusively to `ADMIN_USER_ID`.

2. **Movie Workflow**:
   - `/start` -> Choose "🎬 Movie" -> Input Title & Year (`Movie Name (2024)`).
   - Send media file -> `ffprobe` analyzes streams -> User confirms metadata (`meta_continue`).
   - Download via Telethon -> Save to `{MOVIES_DIR}/{Movie (Year)}/{Movie (Year)}.{ext}`.

3. **TV Show Workflow**:
   - `/start` -> Choose "📺 TV Show" -> Input Show Name -> Input Season number.
   - Send media files sequentially -> Auto-detects/increments episode number `SxxExx`.
   - Save to `{SHOWS_DIR}/{Show Name}/Season {XX}/{Show Name} - S{XX}E{YY}.{ext}`.
   - Send `/stop` when season upload is finished.

4. **Session Persistence & Recovery**:
   - Active workflow state is stored in MongoDB (`sessions` collection).
   - Sending `/start` with an existing active session prompts to **Resume** or **Discard**.

5. **Duplicate Handling**:
   - If destination file already exists, prompts user: `Overwrite` vs `Cancel`.

6. **Interactive File Deletion**:
   - `/delete` opens inline keyboard to navigate movies/shows and safely delete files and database records.

---

## Key Development Rules & Patterns

- **Async Everywhere**: Use `async`/`await` for all I/O, DB, Telegram, and Telethon operations.
- **Plex/Jellyfin Compatibility**: Always follow strict media naming conventions (`Show - S01E01.mkv`, `Movie (2024)/Movie (2024).mp4`).
- **Sanitize Paths**: Use `utils.helpers.sanitize_filename` before constructing filesystem paths.
- **Throttled Progress**: Telegram message edits must be throttled (default ≥5s interval) to prevent rate limits (`FloodWait`).
- **Dependency Injection**: Services and repositories are initialized in `bot.py:post_init` and stored in `app.bot_data`.

---

## Common Commands
- Build & Run: `docker compose up -d --build`
- View Logs: `docker compose logs -f bot`
- Create Telethon Session: `docker compose run --rm bot python create_session.py`
