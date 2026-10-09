from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    admin_user_id: int

    api_id: int
    api_hash: str
    session_file: str = "/app/data/telethon.session"

    telethon_source_chat: str = ""

    mongo_uri: str = "mongodb://mongodb:27017/media_ingestion"

    movies_dir: str = "/mnt/movies_share"
    shows_dir: str = "/mnt/shows_share"

    log_file: str = "/app/logs/app.log"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
