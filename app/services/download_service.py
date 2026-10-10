import asyncio
import logging
import os
import time
from typing import Optional, Dict

from telegram.error import BadRequest
from services.download_tracker import tracker

logger = logging.getLogger(__name__)


def _format_size(size_bytes: float) -> str:
    if size_bytes <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def _format_time(seconds: float) -> str:
    if seconds <= 0:
        return "--"
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours}h {mins:02d}m"
    if mins > 0:
        return f"{mins}m {secs:02d}s"
    return f"{secs}s"


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
        # Map chat_id -> active asyncio.Task for download
        self.active_downloads: Dict[int, asyncio.Task] = {}

    def cancel_download(self, chat_id: int) -> bool:
        task = self.active_downloads.get(chat_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def _resolve_entity(self, client, fallback_chat_id: Optional[int]):
        if self.source_chat:
            try:
                return await client.get_entity(self.source_chat)
            except Exception:
                logger.exception("Failed resolving source_chat=%s", self.source_chat)

        me = await client.get_me()

        if fallback_chat_id is not None:
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
        task_id: Optional[str] = None,
        media_type: str = "media",
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

        # Register in Web UI DownloadTracker
        t_id = task_id or f"{fallback_chat_id}_{message_id}_{int(time.time())}"
        display_name = expected_file_name or os.path.basename(destination_path)
        total_size = expected_file_size or getattr(getattr(source_msg, "file", None), "size", 0) or 0
        tracker.start_download(t_id, display_name, media_type, total_size)

        last_edit_ts = 0.0
        last_percent = -1
        start_mono = time.monotonic()
        last_mono = start_mono
        last_bytes = 0
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
            nonlocal last_edit_ts, last_percent, last_bytes, last_mono
            if total <= 0:
                return

            percent = int((current / total) * 100)
            now_mono = time.monotonic()
            elapsed_interval = now_mono - last_mono

            # Compute current speed
            if elapsed_interval >= 1.0:
                bytes_delta = current - last_bytes
                speed_bps = bytes_delta / elapsed_interval if elapsed_interval > 0 else 0
                last_bytes = current
                last_mono = now_mono
            else:
                elapsed_total = now_mono - start_mono
                speed_bps = current / elapsed_total if elapsed_total > 0 else 0

            speed_str = f"{_format_size(speed_bps)}/s"
            remaining_bytes = max(0, total - current)
            eta_seconds = remaining_bytes / speed_bps if speed_bps > 0 else 0
            eta_str = _format_time(eta_seconds)

            # Update Web UI Tracker
            tracker.update_progress(t_id, current, total, percent, speed_str, eta_str)

            # Throttle Telegram message updates to every 4s
            if percent == last_percent:
                return
            if (now_mono - last_edit_ts) < 4 and percent < 100:
                return

            last_percent = percent
            last_edit_ts = now_mono
            logger.info("Download progress: %s/%s (%s%%) @ %s, ETA: %s", current, total, percent, speed_str, eta_str)
            asyncio.create_task(
                safe_edit(
                    f"Downloading...\n"
                    f"Progress: {percent}%\n"
                    f"Speed: {speed_str}\n"
                    f"ETA: {eta_str}"
                )
            )

        try:
            await client.download_media(
                source_msg,
                file=destination_path,
                progress_callback=progress_callback,
            )
            tracker.set_status(t_id, "processing")
            await safe_edit("Processing & saving media...")
            logger.info("Telethon download completed: %s", destination_path)
        except asyncio.CancelledError:
            tracker.set_status(t_id, "failed", "Cancelled by user")
            if os.path.exists(destination_path):
                try:
                    os.remove(destination_path)
                except Exception:
                    pass
            await safe_edit("❌ Download cancelled.")
            raise
        except Exception as e:
            tracker.set_status(t_id, "failed", str(e))
            raise
