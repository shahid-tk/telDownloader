import asyncio
import logging
import os
import time
import shutil
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from utils.helpers import (
    sanitize_name,
    ensure_dir,
    VALID_VIDEO_EXTENSIONS,
    get_video_extension,
    format_season_episode,
    extract_season_episodes,
    parse_show_info,
)
from utils.ffprobe import extract_metadata, get_format_name, get_show_details
from services.download_tracker import tracker

logger = logging.getLogger(__name__)


class MediaService:
    def __init__(self, settings, session_service, uploads_repo, download_service, media_server_service=None):
        self.settings = settings
        self.session_service = session_service
        self.uploads_repo = uploads_repo
        self.download_service = download_service
        self.media_server_service = media_server_service

        ensure_dir(os.path.join(settings.movies_dir, ".tmp"))
        ensure_dir(os.path.join(settings.shows_dir, ".tmp"))

    async def process_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        media = msg.document or msg.video
        if not media:
            return

        chat_id = update.effective_chat.id
        session = await self.session_service.get(chat_id)

        incoming_name = getattr(media, "file_name", None) or ""
        file_size = getattr(media, "file_size", None)
        file_id = getattr(media, "file_id", None)
        file_unique_id = getattr(media, "file_unique_id", None)

        parsed_show = parse_show_info(incoming_name)

        # Zero-Click Auto-Detection for TV Shows
        if not session:
            if parsed_show:
                await self.session_service.create_show_session(
                    chat_id, parsed_show["title"], parsed_show["season"]
                )
                session = await self.session_service.get(chat_id)
                logger.info(
                    "Auto-created show session for %s Season %02d",
                    parsed_show["title"],
                    parsed_show["season"],
                )
            else:
                await msg.reply_text("No active session. Use /start to select Movie or Show mode.")
                return
        elif session.get("mode") == "show" and parsed_show:
            current_show = session.get("show_name", "")
            current_season = int(session.get("season", 1))
            # If user started sending a new show or new season, auto-update session
            if (
                parsed_show["title"].lower() != current_show.lower()
                or parsed_show["season"] != current_season
            ):
                await self.session_service.create_show_session(
                    chat_id, parsed_show["title"], parsed_show["season"]
                )
                session = await self.session_service.get(chat_id)
                logger.info(
                    "Auto-switched show session to %s Season %02d",
                    parsed_show["title"],
                    parsed_show["season"],
                )

        # 1. Download to temporary path
        base_tmp_dir = self.settings.movies_dir if session["mode"] == "movie" else self.settings.shows_dir
        tmp_dir = os.path.join(base_tmp_dir, ".tmp")
        tmp_filename = f"{chat_id}_{int(time.time())}_{msg.message_id}.tmp"
        tmp_path = os.path.join(tmp_dir, tmp_filename)

        logger.info(
            "\n----------------------------\n"
            "Processing upload\n\n"
            f"Message ID : {msg.message_id}\n"
            f"File ID    : {file_id}\n"
            f"Unique ID  : {file_unique_id}\n"
            f"Filename   : {incoming_name}\n"
            f"Temp Path  : {tmp_path}\n"
            "----------------------------"
        )

        progress_msg = await msg.reply_text("Downloading...")
        logger.info("Download started to temp: %s", tmp_path)

        task_id = f"{chat_id}_{msg.message_id}_{int(time.time())}"
        try:
            await self.download_service.download_from_telethon_chat(
                progress_message=progress_msg,
                destination_path=tmp_path,
                expected_file_name=incoming_name or None,
                fallback_chat_id=chat_id,
                message_id=msg.message_id,
                expected_file_size=file_size,
                task_id=task_id,
                media_type=session.get("mode", "media"),
            )
        except Exception:
            logger.exception("Download failed")
            tracker.set_status(task_id, "failed", "Download failed")
            await progress_msg.edit_text("❌ Download failed.")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return

        # 2. Determine clean video extension
        raw_ext = None
        if incoming_name:
            _, ext_part = os.path.splitext(incoming_name)
            if ext_part and ext_part.lower() in VALID_VIDEO_EXTENSIONS:
                raw_ext = ext_part.lower()

        if raw_ext:
            ext = raw_ext
        else:
            metadata = await extract_metadata(tmp_path)
            fmt_name = get_format_name(metadata) if metadata else None
            ext = get_video_extension(incoming_name, fmt_name)

        # 3. Verify filename or metadata (only for shows)
        warning_msg = None
        extracted_episodes = None

        if session["mode"] == "show":
            expected_show = session["show_name"]
            expected_season = int(session["season"])

            ex_season, ex_episodes = extract_season_episodes(incoming_name)

            # If season/episode could not be parsed from filename, probe media tags
            if ex_season is None or not ex_episodes:
                metadata = await extract_metadata(tmp_path)
                if metadata:
                    _, meta_s, meta_e = get_show_details(metadata)
                    if ex_season is None and meta_s is not None:
                        ex_season = meta_s
                    if not ex_episodes and meta_e is not None:
                        ex_episodes = [meta_e]

            mismatch = False
            if ex_season is not None and ex_season != expected_season:
                mismatch = True
            if not ex_episodes:
                mismatch = True

            extracted_episodes = ex_episodes if ex_episodes else None

            if mismatch:
                detected_ep_str = "-".join(f"E{ep:02d}" for ep in ex_episodes) if ex_episodes else "Unknown"
                warning_msg = (
                    "⚠️ Filename Mismatch\n\n"
                    f"Expected: {expected_show} - Season {expected_season}\n"
                    f"Detected in Filename: Season {ex_season or 'Unknown'} - Episode {detected_ep_str}\n\n"
                    "Do you want to continue?"
                )

        if warning_msg:
            context.user_data["pending_metadata"] = {
                "tmp_path": tmp_path,
                "session": session,
                "episodes": extracted_episodes,
                "ext": ext,
            }
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("Continue", callback_data="meta_continue")],
                [InlineKeyboardButton("Cancel", callback_data="meta_cancel")]
            ])
            await progress_msg.edit_text(warning_msg, reply_markup=kb)
            return

        await self._finalize_save(update, context, tmp_path, session, extracted_episodes, ext, progress_msg)

    async def metadata_decision(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        pending = context.user_data.pop("pending_metadata", None)
        if not pending:
            await query.edit_message_text("No pending metadata decision.")
            return

        tmp_path = pending["tmp_path"]

        if query.data == "meta_cancel":
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            await query.edit_message_text("Upload cancelled.")
            return

        await query.edit_message_text("Continuing upload...")
        await self._finalize_save(
            update,
            context,
            tmp_path,
            pending["session"],
            pending["episodes"],
            pending["ext"],
            query.message,
        )

    async def _finalize_save(self, update, context, tmp_path, session, extracted_episodes, ext, progress_msg):
        # Determine final path
        if session["mode"] == "movie":
            movie_name = sanitize_name(session["movie_name"])
            filename = f"{movie_name}{ext}"
            final_path = os.path.join(self.settings.movies_dir, filename)
        else:
            show_name = sanitize_name(session["show_name"])
            season = int(session["season"])
            episodes = extracted_episodes if extracted_episodes else [int(session["next_episode"])]
            season_dir = os.path.join(self.settings.shows_dir, show_name, f"Season {season:02d}")
            ensure_dir(season_dir)
            filename = format_season_episode(season, episodes, ext)
            final_path = os.path.join(season_dir, filename)

        if os.path.exists(final_path):
            context.user_data["pending_overwrite"] = {
                "tmp_path": tmp_path,
                "filename": filename,
                "path": final_path,
                "session": session,
                "episodes": extracted_episodes,
            }
            kb = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("Yes", callback_data="overwrite_yes"),
                    InlineKeyboardButton("No", callback_data="overwrite_no"),
                ]]
            )
            await progress_msg.edit_text(f"{filename} already exists.\n\nOverwrite?", reply_markup=kb)
            return

        await self._commit_file(
            update.effective_chat.id,
            tmp_path,
            final_path,
            filename,
            session,
            extracted_episodes,
            progress_msg,
        )

    async def overwrite_decision(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        pending = context.user_data.pop("pending_overwrite", None)
        if not pending:
            await query.edit_message_text("No pending overwrite.")
            return

        tmp_path = pending["tmp_path"]

        if query.data == "overwrite_no":
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            await query.edit_message_text("Skipped.")
            return

        await query.edit_message_text("Overwriting...")
        await self._commit_file(
            update.effective_chat.id,
            tmp_path,
            pending["path"],
            pending["filename"],
            pending["session"],
            pending.get("episodes"),
            query.message,
        )

    async def _commit_file(self, chat_id, tmp_path, final_path, filename, session, episodes, progress_msg):
        # Move file to final location
        shutil.move(tmp_path, final_path)

        if session["mode"] == "movie":
            await self.uploads_repo.add_movie(
                movie_name=session["movie_name"],
                filename=filename,
                path=final_path,
            )
            await self.session_service.delete(chat_id)
            await progress_msg.edit_text(f"✅ Saved:\n{filename}")
            logger.info("Movie saved: %s", final_path)
        else:
            season = int(session["season"])
            ep_list = episodes if episodes else [int(session.get("next_episode", 1))]

            for ep in ep_list:
                await self.uploads_repo.delete_episode(session["show_name"], season, ep)
                await self.uploads_repo.add_show(
                    show_name=session["show_name"],
                    season=season,
                    episode=ep,
                    filename=filename,
                    path=final_path,
                )

            max_ep = max(ep_list)
            await self.session_service.update_episode_progress(
                chat_id=chat_id,
                count=len(ep_list),
                next_ep=max_ep + 1,
            )

            await progress_msg.edit_text(
                f"✅ Saved as {filename}\n\n"
                f"Show: {session['show_name']}\n"
                f"Season: {season:02d}\n"
                f"Next expected: e{(max_ep + 1):02d}\n\n"
                f"Send next episode or use /stop when finished."
            )
        # Mark tracker status completed for any task tracking this file
        for t_id, task in list(tracker.active_tasks.items()):
            if task.name == filename or final_path.endswith(task.name):
                tracker.set_status(t_id, "completed")

        # Trigger media server scan in background if configured (silent & non-blocking)
        if self.media_server_service:
            asyncio.create_task(self.media_server_service.trigger_scan())
