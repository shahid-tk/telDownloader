from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import guard_admin


async def menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    q = update.callback_query
    await q.answer()

    if q.data == "mode_movie":
        context.user_data["pending_input"] = "movie_name"
        await q.message.reply_text("Enter movie name:\n\nExample:\nAthiradi (2026)")
        return

    if q.data == "mode_show":
        context.user_data["pending_input"] = "show_name"
        await q.message.reply_text("Enter show name:")
        return


async def unfinished_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    q = update.callback_query
    await q.answer()

    if q.data == "resume":
        await q.message.reply_text("✅ Session resumed. Continue uploading files.")
    elif q.data == "discard":
        await context.application.bot_data["session_service"].delete(update.effective_chat.id)
        await q.message.reply_text("Previous session discarded.")


async def overwrite_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return
    await context.application.bot_data["media_service"].overwrite_decision(update, context)
