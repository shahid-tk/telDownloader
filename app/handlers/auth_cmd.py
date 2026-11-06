import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import settings
from utils.auth import guard_admin

logger = logging.getLogger(__name__)


async def reset_web_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    new_pwd = ""
    if context.args:
        new_pwd = " ".join(context.args).strip()

    settings.web_password = new_pwd

    # Update .env
    for env_path in ("/app/.env", ".env"):
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                updated = False
                new_lines = []
                for line in lines:
                    if line.startswith("WEB_PASSWORD="):
                        new_lines.append(f"WEB_PASSWORD={new_pwd}\n")
                        updated = True
                    else:
                        new_lines.append(line)
                if not updated:
                    new_lines.append(f"WEB_PASSWORD={new_pwd}\n")
                with open(env_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
            except Exception as e:
                logger.error(f"Failed to update {env_path}: {e}")

    user = settings.web_username or "admin"
    if new_pwd:
        msg = (
            f"🔐 *Web Password Updated!*\n\n"
            f"• *Username:* `{user}`\n"
            f"• *Password:* `{new_pwd}`\n\n"
            f"Sign in at the web dashboard with this new password."
        )
    else:
        msg = (
            f"🔓 *Web Password Reset!*\n\n"
            f"• *Username:* `{user}`\n"
            f"• *Password:* _(empty / no password)_\n\n"
            f"Sign in at the web dashboard by entering `{user}` and leaving the password field blank."
        )

    await update.effective_message.reply_text(msg, parse_mode="Markdown")
