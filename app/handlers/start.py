import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler
from utils.auth import guard_admin

logger = logging.getLogger(__name__)

MENU_STATE = 0
ASK_MOVIE_NAME = 1
ASK_SHOW_NAME = 2
ASK_SEASON = 3
UNFINISHED_CHOICE = 4


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    session = None
    try:
        session = await context.application.bot_data["session_service"].get(chat_id)
    except Exception:
        logger.exception("Failed getting session for chat_id=%s", chat_id)

    if session and session.get("mode"):
        try:
            if session.get("mode") == "show":
                show_name = session.get("show_name") or "Unknown Show"
                try:
                    season_num = int(session.get("season") or 1)
                    season_str = f"{season_num:02d}"
                except (ValueError, TypeError):
                    season_str = "01"

                try:
                    next_ep = int(session.get("next_episode") or 1)
                    next_ep_str = f"{next_ep:02d}"
                except (ValueError, TypeError):
                    next_ep_str = "01"

                text = (
                    "Unfinished session found.\n\n"
                    f"Show: {show_name}\n"
                    f"Season: {season_str}\n"
                    f"Next Episode: {next_ep_str}"
                )
            else:
                movie_name = session.get("movie_name") or "Unknown Movie"
                text = (
                    "Unfinished session found.\n\n"
                    f"Movie: {movie_name}\n"
                    "Status: Waiting For File"
                )

            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("Resume", callback_data="resume"),
                InlineKeyboardButton("Discard", callback_data="discard"),
            ]])
            await update.effective_message.reply_text(text, reply_markup=kb)
            return UNFINISHED_CHOICE
        except Exception:
            logger.exception("Error rendering unfinished session, clearing stale session")
            try:
                await context.application.bot_data["session_service"].delete(chat_id)
            except Exception:
                pass

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Movies", callback_data="mode_movie")],
        [InlineKeyboardButton("📺 Shows", callback_data="mode_show")],
    ])
    await update.effective_message.reply_text("Choose mode:", reply_markup=kb)
    return MENU_STATE
