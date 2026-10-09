# Telegram Media Ingestion Bot

Production-ready admin-only Telegram media ingestion bot using:

- python-telegram-bot
- Telethon user session
- MongoDB + Motor
- Docker + Docker Compose

## Features

- Admin-only (single `ADMIN_USER_ID`)
- Movie + Show workflows
- Session persistence in MongoDB
- Resume/discard unfinished session
- Telethon large-file downloads with progress updates (~5s)
- Duplicate detection with overwrite prompt
- Plex/Jellyfin-compatible naming

## Directory Layout (inside host)

- `/mnt/share_movies`
- `/mnt/share_shows`
- `./data` (Telethon session persistence)
- `./logs` (bot logs)

## Quick Start

1. Clone project
2. Copy environment:
   ```bash
   cp .env.example .env
   ```
3. Fill `.env`:
   - BOT_TOKEN
   - API_ID
   - API_HASH
   - ADMIN_USER_ID

4. Create Telethon session **once**:
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

## Commands

- `/start`
- `/help`
- `/status`
- `/cancel`
- `/stop`

## Security

Every command, callback, and upload is validated against `ADMIN_USER_ID`.
Unauthorized users always get:

`⛔ Unauthorized`

## Production Deployment Notes

- Keep `./data/telethon.session` backed up.
- Restrict permissions on `./data` and media mount points.
- Keep MongoDB volume backups (`mongo_data`).
- Use a reverse proxy/firewall on the host as needed.
- Ensure server clock/timezone are correct.

## Troubleshooting

### Session missing
If bot fails at startup with session missing error:

```bash
docker compose run --rm bot python create_session.py
```

### Unauthorized errors
Check `ADMIN_USER_ID` exactly matches your Telegram numeric user ID.

### Mongo connection issue
Verify `MONGO_URI` and container health:
```bash
docker compose ps
docker compose logs -f mongodb
```