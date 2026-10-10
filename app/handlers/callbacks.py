from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from utils.auth import guard_admin
from utils.helpers import (
    get_all_available_shows,
    get_available_seasons,
    get_next_expected_episode,
)

PAGE_SIZE = 8


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
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ New Show", callback_data="show_new")],
            [InlineKeyboardButton("▶️ Continue upload", callback_data="show_cont|0")],
        ])
        await q.edit_message_text("Choose show upload mode:", reply_markup=kb)
        return


async def show_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    q = update.callback_query
    await q.answer()
    data = q.data

    uploads_repo = context.application.bot_data["media_service"].uploads_repo
    shows_dir = context.application.bot_data["settings"].shows_dir

    if data == "show_new":
        context.user_data["pending_input"] = "show_name"
        await q.message.reply_text("Enter show name:")
        return

    elif data.startswith("show_cont|"):
        _, page_str = data.split("|", 1)
        page = int(page_str)

        shows = await get_all_available_shows(uploads_repo, shows_dir)
        if not shows:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ New Show", callback_data="show_new")]
            ])
            await q.edit_message_text("No existing shows found. Create a new show:", reply_markup=kb)
            return

        # Store shows in user_data for quick lookup and short callback_data
        context.user_data["available_shows"] = shows

        total_shows = len(shows)
        start_idx = page * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, total_shows)
        page_shows = shows[start_idx:end_idx]

        kb = []
        for i, show_name in enumerate(page_shows, start=start_idx):
            kb.append([InlineKeyboardButton(show_name, callback_data=f"show_sel|{i}")])

        # Pagination row
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"show_cont|{page - 1}"))
        if end_idx < total_shows:
            nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"show_cont|{page + 1}"))

        if nav_buttons:
            kb.append(nav_buttons)

        kb.append([InlineKeyboardButton("➕ New Show", callback_data="show_new")])

        page_info = f" (Page {page + 1}/{(total_shows + PAGE_SIZE - 1) // PAGE_SIZE})" if total_shows > PAGE_SIZE else ""
        await q.edit_message_text(f"Select a show to continue{page_info}:", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data.startswith("show_sel|"):
        _, idx_str = data.split("|", 1)
        idx = int(idx_str)

        shows = context.user_data.get("available_shows")
        if not shows or idx >= len(shows):
            shows = await get_all_available_shows(uploads_repo, shows_dir)
            context.user_data["available_shows"] = shows

        if idx >= len(shows):
            await q.edit_message_text("Show not found. Please try again with /start.")
            return

        show_name = shows[idx]
        context.user_data["show_name"] = show_name

        seasons = await get_available_seasons(uploads_repo, shows_dir, show_name)

        kb = []
        for s in seasons:
            kb.append([InlineKeyboardButton(f"Season {s:02d}", callback_data=f"show_season|{idx}|{s}")])

        kb.append([InlineKeyboardButton("➕ New Season", callback_data=f"show_season_new|{idx}")])
        kb.append([InlineKeyboardButton("🔙 Back to Shows", callback_data="show_cont|0")])

        await q.edit_message_text(
            f"Show: {show_name}\nSelect season or add a new season:",
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    elif data.startswith("show_season|"):
        _, idx_str, season_str = data.split("|", 2)
        idx = int(idx_str)
        season = int(season_str)

        shows = context.user_data.get("available_shows")
        if not shows or idx >= len(shows):
            shows = await get_all_available_shows(uploads_repo, shows_dir)
            context.user_data["available_shows"] = shows

        show_name = shows[idx] if idx < len(shows) else context.user_data.get("show_name")
        if not show_name:
            await q.edit_message_text("Show not found. Please try again with /start.")
            return

        next_ep = await get_next_expected_episode(uploads_repo, shows_dir, show_name, season)

        await context.application.bot_data["session_service"].create_show_session(
            chat_id=update.effective_chat.id,
            show_name=show_name,
            season=season,
            next_episode=next_ep,
        )

        context.user_data.pop("pending_input", None)

        await q.edit_message_text(
            f"▶️ Continuing {show_name}\n"
            f"Season: {season:02d}\n"
            f"Next episode: e{next_ep:02d}\n\n"
            "Send all episode files.\n"
            "Episodes will be numbered automatically.\n\n"
            "Use /stop when finished."
        )
        return

    elif data.startswith("show_season_new|"):
        _, idx_str = data.split("|", 1)
        idx = int(idx_str)

        shows = context.user_data.get("available_shows")
        if not shows or idx >= len(shows):
            shows = await get_all_available_shows(uploads_repo, shows_dir)
            context.user_data["available_shows"] = shows

        show_name = shows[idx] if idx < len(shows) else context.user_data.get("show_name")
        if not show_name:
            await q.edit_message_text("Show not found. Please try again with /start.")
            return

        context.user_data["show_name"] = show_name
        context.user_data["pending_input"] = "season"

        await q.edit_message_text(f"Show: {show_name}\nEnter season number:")
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
