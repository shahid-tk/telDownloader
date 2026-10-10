from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import guard_admin


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    chat_id = update.effective_chat.id

    # 1. Cancel active download if running
    media_service = context.application.bot_data.get("media_service")
    download_cancelled = False
    if media_service and getattr(media_service, "download_service", None):
        download_cancelled = media_service.download_service.cancel_download(chat_id)

    # 2. Delete active session
    await context.application.bot_data["session_service"].delete(chat_id)
    context.user_data.clear()

    if download_cancelled:
        await update.effective_message.reply_text("🛑 Active download cancelled and session cleared.")
    else:
        await update.effective_message.reply_text("Current upload session cancelled.")
