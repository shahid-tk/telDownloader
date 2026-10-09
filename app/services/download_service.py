import asyncio
import logging
import os
import time
from typing import Optional

from telegram.error import BadRequest

logger = logging.getLogger(__name__)


class DownloadService:
    def __init__(self, telethon_service, source_chat: Optional[str] = None):
        self.telethon_service = telethon_service
        self.source_chat = source_chat

    async def _resolve_entity(self, client, fallback_chat_id: Optional[int]):
        if self.source_chat:
            try:
                return await client.get_entity(self.source_chat)
            except Exception:
                logger.exception("Failed resolving source_chat=%s", self.source_chat)

        if fallback_chat_id is not None:
            try:
                return await client.get_entity(int(fallback_chat_id))
            except Exception:
                logger.exception("Failed resolving fallback_chat_id=%s", fallback_chat_id)

        try:
            return await client.get_entity("me")
        except Exception:
            logger.exception("Failed resolving Saved Messages (me)")
            return None

    async def download_from_telethon_chat(
        self,
        *,
        progress_message,
        destination_path: str,
        expected_file_name: Optional[str] = None,
        fallback_chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        expected_file_size: Optional[int] = None,
    ) -> None:
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        client = self.telethon_service.client
        if not client:
            raise RuntimeError("Telethon client not initialized")

        entity = await self._resolve_entity(client, fallback_chat_id)
        if entity is None:
            raise RuntimeError("Unable to resolve any Telethon source entity")

        source_msg = None
        
        # 1. Try to fetch the exact message by ID if we are in the same chat
        if message_id and not self.source_chat:
            try:
                m = await client.get_messages(entity, ids=message_id)
                if m and m.media:
                    source_msg = m
            except Exception:
                logger.warning("Failed to fetch message by ID %s", message_id)

        # 2. Fallback to searching the chat history
        if not source_msg:
            async for m in client.iter_messages(entity, limit=100):
                if not m or not m.media:
                    continue

                m_name = getattr(getattr(m, "file", None), "name", None)
                m_size = getattr(getattr(m, "file", None), "size", None)

                if expected_file_name and m_name and m_name.lower() == expected_file_name.lower():
                    source_msg = m
                    break
                    
                if expected_file_size and m_size == expected_file_size:
                    source_msg = m
                    break

        if source_msg is None:
            raise RuntimeError(f"No matching media message found in resolved Telethon chat. (Name: {expected_file_name}, Size: {expected_file_size})")

        last_edit_ts = 0.0
        last_percent = -1
        last_text = None

        async def safe_edit(text: str):
            nonlocal last_text
            if text == last_text:
                return
            try:
                await progress_message.edit_text(text)
                last_text = text
            except BadRequest as e:
                if "message is not modified" in str(e).lower():
                    return
                logger.exception("Failed to edit progress message")
            except Exception:
                logger.exception("Failed to edit progress message")

        await safe_edit("Downloading...\n0%")
        logger.info("Telethon download started: msg_id=%s dest=%s", source_msg.id, destination_path)

        def progress_callback(current: int, total: int):
            nonlocal last_edit_ts, last_percent
            if total <= 0:
                return

            percent = int((current / total) * 100)
            now = time.monotonic()

            if percent == last_percent:
                return
            if (now - last_edit_ts) < 5 and percent < 100:
                return

            last_percent = percent
            last_edit_ts = now
            logger.info("Download progress: %s/%s (%s%%)", current, total, percent)
            asyncio.create_task(safe_edit(f"Downloading...\n{percent}%"))

        await client.download_media(
            source_msg,
            file=destination_path,
            progress_callback=progress_callback,
        )

        await safe_edit("Downloading...\n100%")
        logger.info("Telethon download completed: %s", destination_path)
