import asyncio
import logging
import os
import time
from typing import Optional

from telegram.error import BadRequest

logger = logging.getLogger(__name__)


class DownloadService:
    def __init__(
        self,
        telethon_service,
        source_chat: Optional[str] = None,
        bot_id: Optional[int] = None,
    ):
        self.telethon_service = telethon_service
        self.source_chat = source_chat
        self.bot_id = bot_id

    async def _resolve_entity(self, client, fallback_chat_id: Optional[int]):
        """
        Resolves the Telegram entity from Telethon's perspective.
        - If source_chat is set in config, prioritize that.
        - When a user chats privately with the bot, fallback_chat_id is the user's ID.
          Since Telethon is logged in as that same user, asking for user_id would resolve
          to 'Saved Messages' (chat with oneself). We must resolve the BOT entity instead!
        - For group chats (negative IDs), resolve the group chat ID directly.
        """
        if self.source_chat:
            try:
                return await client.get_entity(self.source_chat)
            except Exception:
                logger.exception("Failed resolving source_chat=%s", self.source_chat)

        me = await client.get_me()

        if fallback_chat_id is not None:
            # Check if this is a private chat between the user and the bot
            if me and int(fallback_chat_id) == me.id:
                if self.bot_id:
                    try:
                        return await client.get_entity(int(self.bot_id))
                    except Exception:
                        logger.exception("Failed resolving bot_id=%s", self.bot_id)
            else:
                try:
                    return await client.get_entity(int(fallback_chat_id))
                except Exception:
                    logger.exception("Failed resolving fallback_chat_id=%s", fallback_chat_id)

        if self.bot_id:
            try:
                return await client.get_entity(int(self.bot_id))
            except Exception:
                pass

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
        clean_exp_name = expected_file_name.strip().lower() if expected_file_name else None

        # Search recent messages in the resolved chat (limit 50)
        # Pass 1: Strict match (both filename and file size match)
        if clean_exp_name and expected_file_size:
            async for m in client.iter_messages(entity, limit=50):
                if not m or not m.media:
                    continue
                m_name = getattr(getattr(m, "file", None), "name", None)
                m_size = getattr(getattr(m, "file", None), "size", None)
                if (
                    m_name
                    and m_name.strip().lower() == clean_exp_name
                    and m_size == expected_file_size
                ):
                    source_msg = m
                    logger.info("Found exact match by name and size: msg_id=%s file=%s", m.id, m_name)
                    break

        # Pass 2: Match by filename or size
        if not source_msg:
            async for m in client.iter_messages(entity, limit=50):
                if not m or not m.media:
                    continue
                m_name = getattr(getattr(m, "file", None), "name", None)
                m_size = getattr(getattr(m, "file", None), "size", None)

                if clean_exp_name and m_name and m_name.strip().lower() == clean_exp_name:
                    source_msg = m
                    logger.info("Found match by filename: msg_id=%s file=%s", m.id, m_name)
                    break

                if expected_file_size and m_size == expected_file_size:
                    source_msg = m
                    logger.info("Found match by file size: msg_id=%s size=%s", m.id, m_size)
                    break

        # Pass 3: Fallback for media sent without filename (e.g. video streams)
        if not source_msg and not self.source_chat:
            async for m in client.iter_messages(entity, limit=5):
                if m and m.media:
                    source_msg = m
                    logger.info("Found latest media fallback: msg_id=%s", m.id)
                    break

        if source_msg is None:
            raise RuntimeError(
                f"No matching media message found in chat. (Name: {expected_file_name}, Size: {expected_file_size})"
            )

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
