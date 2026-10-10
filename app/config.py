from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    admin_user_id: int

    api_id: int
    api_hash: str
    session_file: str = "/app/data/telethon.session"

    telethon_source_chat: str = ""

    sqlite_path: str = "/app/data/media_data.db"

    movies_dir: str = "/media/jellyfinData/movies"
    shows_dir: str = "/media/jellyfinData/shows"

    # Optional Media Servers
    jellyfin_url: str = ""
    jellyfin_api_key: str = ""
    plex_url: str = ""
    plex_token: str = ""

    # Web Dashboard
    web_host: str = "0.0.0.0"
    web_port: int = 8088

    log_file: str = "/app/logs/app.log"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
