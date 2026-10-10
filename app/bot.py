import asyncio
import logging
import uvicorn
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import settings
from utils.logger import setup_logger
from utils.helpers import ensure_dir

from database.sqlite import Database
from database.repositories.users_repo import UsersRepository
from database.repositories.sessions_repo import SessionsRepository
from database.repositories.uploads_repo import UploadsRepository

from services.session_service import SessionService
from services.telethon_service import TelethonService
from services.download_service import DownloadService
from services.media_service import MediaService
from services.media_server import MediaServerService

from handlers.start import start_command
from handlers.movie import ask_movie_name
from handlers.show import ask_show_name, ask_season
from handlers.status import status_command
from handlers.cancel import cancel_command
from handlers.callbacks import (
    menu_callbacks,
    unfinished_callbacks,
    overwrite_callbacks,
    show_callbacks,
)

from web.server import app as web_app

logger = logging.getLogger(__name__)


async def help_command(update, context):
    from utils.auth import guard_admin
    if not await guard_admin(update, context):
        return
    await update.effective_message.reply_text("/start\n/status\n/cancel\n/stop\n/help")


async def stop_command(update, context):
    from utils.auth import guard_admin
    if not await guard_admin(update, context):
        return

    session = await context.application.bot_data["session_service"].get(update.effective_chat.id)
    if not session or session.get("mode") != "show":
        await update.effective_message.reply_text("No active show session.")
        return

    reply = (
        "✅ Season upload completed\n\n"
        f"Show: {session['show_name']}\n"
        f"Season: {int(session['season']):02d}\n"
        f"Episodes Uploaded: {int(session.get('episodes_uploaded', 0))}"
    )
    await context.application.bot_data["session_service"].delete(update.effective_chat.id)
    await update.effective_message.reply_text(reply)


async def media_handler(update, context):
    from utils.auth import guard_admin
    if not await guard_admin(update, context):
        return
    await context.application.bot_data["media_service"].process_media(update, context)


async def text_router(update, context):
    from utils.auth import guard_admin
    if not await guard_admin(update, context):
        return

    pending = context.user_data.get("pending_input")

    if pending == "movie_name":
        await ask_movie_name(update, context)
        context.user_data.pop("pending_input", None)
        return

    if pending == "show_name":
        await ask_show_name(update, context)
        return

    if pending == "season":
        await ask_season(update, context)
        return

    session = await context.application.bot_data["session_service"].get(update.effective_chat.id)
    if not session:
        await update.effective_message.reply_text("No active session. Use /start")
        return

    await update.effective_message.reply_text("Send media file or use /status /cancel /stop")


async def on_error(update, context):
    logger.exception("Unhandled exception", exc_info=context.error)
    try:
        if update and getattr(update, "effective_message", None):
            await update.effective_message.reply_text("❌ Error while processing. Please try again.")
    except Exception:
        pass


async def post_init(app: Application):
    logger.info("startup")

    ensure_dir("/app/data")
    ensure_dir("/app/logs")
    ensure_dir(settings.movies_dir)
    ensure_dir(settings.shows_dir)

    db = Database(settings.sqlite_path)
    await db.connect()

    users_repo = UsersRepository(db.conn)
    sessions_repo = SessionsRepository(db.conn)
    uploads_repo = UploadsRepository(db.conn)

    session_service = SessionService(sessions_repo)
    telethon_service = TelethonService(settings.api_id, settings.api_hash, settings.session_file)
    await telethon_service.start()

    bot_id = int(settings.bot_token.split(":")[0])
    download_service = DownloadService(
        telethon_service, settings.telethon_source_chat, bot_id=bot_id
    )

    media_server_service = MediaServerService(
        jellyfin_url=settings.jellyfin_url,
        jellyfin_api_key=settings.jellyfin_api_key,
        plex_url=settings.plex_url,
        plex_token=settings.plex_token,
    )
    media_service = MediaService(
        settings, session_service, uploads_repo, download_service, media_server_service
    )

    await users_repo.ensure_admin(settings.admin_user_id)

    app.bot_data["settings"] = settings
    app.bot_data["db"] = db
    app.bot_data["session_service"] = session_service
    app.bot_data["media_service"] = media_service

    logger.info("startup complete")


async def post_shutdown(app: Application):
    logger.info("shutdown")

    media_service = app.bot_data.get("media_service")
    if media_service and getattr(media_service, "download_service", None):
        telethon_service = getattr(media_service.download_service, "telethon_service", None)
        if telethon_service:
            await telethon_service.stop()

    db = app.bot_data.get("db")
    if db:
        await db.close()


def build_application() -> Application:
    app = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    from handlers.delete import delete_command
    from handlers.delete_callbacks import delete_callbacks

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("delete", delete_command))

    app.add_handler(CallbackQueryHandler(menu_callbacks, pattern="^(mode_movie|mode_show)$"))
    app.add_handler(CallbackQueryHandler(show_callbacks, pattern="^(show_new|show_cont\\||show_sel\\||show_season\\||show_season_new\\|)"))
    app.add_handler(CallbackQueryHandler(unfinished_callbacks, pattern="^(resume|discard)$"))
    app.add_handler(CallbackQueryHandler(overwrite_callbacks, pattern="^(overwrite_yes|overwrite_no)$"))

    async def meta_callbacks(update, context):
        from utils.auth import guard_admin
        if not await guard_admin(update, context):
            return
        await context.application.bot_data["media_service"].metadata_decision(update, context)

    app.add_handler(CallbackQueryHandler(meta_callbacks, pattern="^(meta_continue|meta_cancel)$"))
    app.add_handler(CallbackQueryHandler(delete_callbacks, pattern="^del_"))

    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO, media_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.add_error_handler(on_error)

    return app


async def run_all():
    setup_logger(settings.log_file, settings.log_level)
    bot_app = build_application()

    # Configure Uvicorn web server
    config = uvicorn.Config(
        web_app,
        host=settings.web_host,
        port=settings.web_port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(config)

    # Initialize and start bot application
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(allowed_updates=["message", "callback_query"])

    logger.info("Web dashboard running on http://%s:%s", settings.web_host, settings.web_port)

    # Run web server concurrently with bot polling
    try:
        await server.serve()
    finally:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(run_all())
    except (KeyboardInterrupt, SystemExit):
        pass
