import asyncio
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
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self.client and self.client.is_connected():
                return

            if not os.path.exists(self.session_file):
                raise RuntimeError(
                    f"Telethon session file missing: {self.session_file}. "
                    f"Run create_session.py first."
                )

            if not self.client:
                self.client = TelegramClient(
                    self.session_file,
                    self.api_id,
                    self.api_hash,
                    timeout=30,
                    connection_retries=5,
                    retry_delay=2,
                    auto_reconnect=True,
                )

            if not self.client.is_connected():
                await self.client.connect()

            if not await self.client.is_user_authorized():
                raise RuntimeError(
                    "Telethon session is not authorized. Recreate with create_session.py."
                )
            logger.info("Telethon user session connected successfully")

    async def ensure_connected(self) -> TelegramClient:
        async with self._lock:
            if not self.client:
                if not os.path.exists(self.session_file):
                    raise RuntimeError(f"Telethon session file missing: {self.session_file}")
                self.client = TelegramClient(
                    self.session_file,
                    self.api_id,
                    self.api_hash,
                    timeout=30,
                    connection_retries=5,
                    retry_delay=2,
                    auto_reconnect=True,
                )

            if not self.client.is_connected():
                logger.warning("Telethon client disconnected. Reconnecting...")
                try:
                    await self.client.connect()
                except Exception as e:
                    logger.error("Failed to connect Telethon client: %s", e)
                    raise

                if not await self.client.is_user_authorized():
                    raise RuntimeError("Telethon session is not authorized.")
                logger.info("Telethon client successfully reconnected.")

            return self.client

    async def stop(self) -> None:
        async with self._lock:
            if self.client:
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
                logger.info("Telethon client disconnected")
