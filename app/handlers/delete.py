from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from utils.auth import guard_admin


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Delete Movie", callback_data="del_movies_list")],
        [InlineKeyboardButton("📺 Delete Show", callback_data="del_shows_list")],
    ])
    await update.effective_message.reply_text("What would you like to delete?", reply_markup=kb)
