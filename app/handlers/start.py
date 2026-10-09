from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler
from utils.auth import guard_admin

MENU_STATE = 0
ASK_MOVIE_NAME = 1
ASK_SHOW_NAME = 2
ASK_SEASON = 3
UNFINISHED_CHOICE = 4


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    session = await context.application.bot_data["session_service"].get(chat_id)

    if session:
        if session["mode"] == "show":
            text = (
                "Unfinished session found.\n\n"
                f"Show: {session['show_name']}\n"
                f"Season: {int(session['season']):02d}\n"
                f"Next Episode: {int(session['next_episode']):02d}"
            )
        else:
            text = (
                "Unfinished session found.\n\n"
                f"Movie: {session['movie_name']}\n"
                "Status: Waiting For File"
            )

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Resume", callback_data="resume"),
            InlineKeyboardButton("Discard", callback_data="discard"),
        ]])
        await update.effective_message.reply_text(text, reply_markup=kb)
        return UNFINISHED_CHOICE

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Movies", callback_data="mode_movie")],
        [InlineKeyboardButton("📺 Shows", callback_data="mode_show")],
    ])
    await update.effective_message.reply_text("Choose mode:", reply_markup=kb)
    return MENU_STATE
