import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import guard_admin

logger = logging.getLogger(__name__)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    chat_id = update.effective_chat.id
    session = None
    try:
        session = await context.application.bot_data["session_service"].get(chat_id)
    except Exception:
        logger.exception("Failed getting session for chat_id=%s", chat_id)

    # Check if download is active
    media_service = context.application.bot_data.get("media_service")
    is_downloading = False
    if media_service and getattr(media_service, "download_service", None):
        is_downloading = chat_id in media_service.download_service.active_downloads

    download_status_extra = "\n\n⚡ Active download in progress!" if is_downloading else ""

    if not session or not session.get("mode"):
        if is_downloading:
            await update.effective_message.reply_text(f"No active session configured.{download_status_extra}\nUse /cancel to stop download.")
        else:
            await update.effective_message.reply_text("No active session. Use /start")
        return

    try:
        if session.get("mode") == "movie":
            movie_name = session.get("movie_name") or "Unknown Movie"
            text = (
                "Current Session\n\n"
                "Mode: Movie\n"
                f"Movie: {movie_name}\n\n"
                f"Status: {'Downloading' if is_downloading else 'Waiting For File'}"
                f"{download_status_extra}"
            )
        else:
            show_name = session.get("show_name") or "Unknown Show"
            try:
                season_num = int(session.get("season") or 1)
                season_str = f"{season_num:02d}"
            except (ValueError, TypeError):
                season_str = "01"

            try:
                uploaded_num = int(session.get("episodes_uploaded") or 0)
            except (ValueError, TypeError):
                uploaded_num = 0

            try:
                next_ep_num = int(session.get("next_episode") or 1)
                next_ep_str = f"{next_ep_num:02d}"
            except (ValueError, TypeError):
                next_ep_str = "01"

            text = (
                "Current Session\n\n"
                "Mode: Show\n"
                f"Show: {show_name}\n"
                f"Season: {season_str}\n\n"
                f"Episodes Uploaded: {uploaded_num}\n"
                f"Next Episode: {next_ep_str}\n\n"
                f"Status: {'Downloading' if is_downloading else 'Uploading'}"
                f"{download_status_extra}"
            )

        await update.effective_message.reply_text(text)
    except Exception:
        logger.exception("Error in status_command")
        await update.effective_message.reply_text("Current session active. Send media or use /cancel.")
