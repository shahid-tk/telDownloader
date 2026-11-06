from telegram import Update
from telegram.ext import ContextTypes
from config import settings


def is_admin(update: Update, admin_user_id: int) -> bool:
    user = update.effective_user
    return bool(user and user.id == admin_user_id)


async def guard_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    bot_settings = context.application.bot_data.get("settings") if hasattr(context, "application") and context.application else None
    admin_id = getattr(bot_settings, "admin_user_id", None) or settings.admin_user_id

    if not is_admin(update, admin_id):
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Unauthorized")
        elif update.callback_query:
            await update.callback_query.answer("⛔ Unauthorized", show_alert=True)
        return False
    return True
