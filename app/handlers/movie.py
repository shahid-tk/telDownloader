from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from utils.auth import guard_admin
from utils.helpers import sanitize_name


async def ask_movie_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return ConversationHandler.END

    movie_name = sanitize_name(update.effective_message.text)
    await context.application.bot_data["session_service"].create_movie_session(
        update.effective_chat.id,
        movie_name,
    )
    await update.effective_message.reply_text("Send movie file.")
    return ConversationHandler.END