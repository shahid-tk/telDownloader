import logging
import os
from telethon import TelegramClient

logger = logging.getLogger(__name__)


class TelethonService:
    def __init__(self, api_id: int, api_hash: str, session_file: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_file = session_file
        self.client: TelegramClient | None = None

    async def start(self) -> None:
        if not os.path.exists(self.session_file):
            raise RuntimeError(
                f"Telethon session file missing: {self.session_file}. "
                f"Run create_session.py first."
            )

        self.client = TelegramClient(self.session_file, self.api_id, self.api_hash)
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError(
                "Telethon session is not authorized. Recreate with create_session.py."
            )
        logger.info("Telethon user session connected successfully")

    async def stop(self) -> None:
        if self.client:
            await self.client.disconnect()
            logger.info("Telethon client disconnected")