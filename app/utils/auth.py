from telegram import Update
from telegram.ext import ContextTypes


def is_admin(update: Update, admin_user_id: int) -> bool:
    user = update.effective_user
    return bool(user and user.id == admin_user_id)


async def guard_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not is_admin(update, context.application.bot_data["settings"].admin_user_id):
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Unauthorized")
        elif update.callback_query:
            await update.callback_query.answer("⛔ Unauthorized", show_alert=True)
        return False
    return True