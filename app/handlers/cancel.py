from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import guard_admin


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return
    await context.application.bot_data["session_service"].delete(update.effective_chat.id)
    await update.effective_message.reply_text("Current upload session cancelled.")