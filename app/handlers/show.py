from telegram import Update
from telegram.ext import ContextTypes
from utils.auth import guard_admin
from utils.helpers import sanitize_name


async def ask_show_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    context.user_data["show_name"] = sanitize_name(update.effective_message.text)
    context.user_data["pending_input"] = "season"
    await update.effective_message.reply_text("Enter season number:")


async def ask_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    text = update.effective_message.text.strip()
    if not text.isdigit():
        await update.effective_message.reply_text("Season must be a number. Enter season number:")
        return

    season = int(text)
    show_name = context.user_data["show_name"]
    await context.application.bot_data["session_service"].create_show_session(
        update.effective_chat.id,
        show_name,
        season,
    )

    context.user_data.pop("pending_input", None)

    await update.effective_message.reply_text(
        f"Season {season:02d} selected.\n\n"
        "Send all episode files.\n\n"
        "Episodes will be numbered automatically.\n\n"
        "Use /stop when finished."
    )
