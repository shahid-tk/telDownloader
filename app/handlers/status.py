from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import guard_admin


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    session = await context.application.bot_data["session_service"].get(update.effective_chat.id)
    if not session:
        await update.effective_message.reply_text("No active session.")
        return

    if session["mode"] == "movie":
        text = (
            "Current Session\n\n"
            "Mode: Movie\n"
            f"Movie: {session['movie_name']}\n\n"
            "Status: Waiting For File"
        )
    else:
        text = (
            "Current Session\n\n"
            "Mode: Show\n"
            f"Show: {session['show_name']}\n"
            f"Season: {int(session['season']):02d}\n\n"
            f"Episodes Uploaded: {int(session.get('episodes_uploaded', 0))}\n"
            f"Next Episode: {int(session['next_episode']):02d}\n\n"
            "Status: Uploading"
        )

    await update.effective_message.reply_text(text)