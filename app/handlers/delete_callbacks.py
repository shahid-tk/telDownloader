import asyncio
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from utils.auth import guard_admin
from utils.helpers import remove_empty_dirs


async def delete_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard_admin(update, context):
        return

    q = update.callback_query
    await q.answer()

    data = q.data
    media_service = context.application.bot_data["media_service"]
    uploads_repo = media_service.uploads_repo
    media_server_service = getattr(media_service, "media_server_service", None)

    if data == "del_movies_list":
        movies = await uploads_repo.get_movies()
        if not movies:
            await q.edit_message_text("No movies found.")
            return

        kb = []
        for m in movies:
            kb.append([InlineKeyboardButton(m, callback_data=f"del_movie_confirm|{m}")])
        await q.edit_message_text("Select a movie to delete:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_movie_confirm|"):
        _, movie_name = data.split("|", 1)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes, Delete", callback_data=f"del_movie_do|{movie_name}")],
            [InlineKeyboardButton("Cancel", callback_data="del_cancel")]
        ])
        await q.edit_message_text(f"Are you sure you want to delete movie:\n{movie_name}", reply_markup=kb)

    elif data.startswith("del_movie_do|"):
        _, movie_name = data.split("|", 1)
        path = await uploads_repo.get_movie_path(movie_name)
        if path and os.path.exists(path):
            os.remove(path)
        
        await uploads_repo.delete_movie(movie_name)
        await q.edit_message_text(f"✅ Deleted movie: {movie_name}")

        if media_server_service:
            asyncio.create_task(media_server_service.trigger_scan())

    elif data == "del_shows_list":
        shows = await uploads_repo.get_shows()
        if not shows:
            await q.edit_message_text("No shows found.")
            return

        kb = []
        for s in shows:
            kb.append([InlineKeyboardButton(s, callback_data=f"del_show_seasons|{s}")])
        await q.edit_message_text("Select a show:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_show_seasons|"):
        _, show_name = data.split("|", 1)
        seasons = await uploads_repo.get_show_seasons(show_name)
        
        kb = [[InlineKeyboardButton("Delete Entire Show", callback_data=f"del_show_confirm|{show_name}")]]
        for s in sorted(seasons):
            kb.append([InlineKeyboardButton(f"Season {s}", callback_data=f"del_show_episodes|{show_name}|{s}")])
            
        await q.edit_message_text(f"Show: {show_name}\nSelect season or delete entire show:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_show_confirm|"):
        _, show_name = data.split("|", 1)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes, Delete Show", callback_data=f"del_show_do|{show_name}")],
            [InlineKeyboardButton("Cancel", callback_data="del_cancel")]
        ])
        await q.edit_message_text(f"Are you sure you want to delete ENTIRE SHOW:\n{show_name}", reply_markup=kb)

    elif data.startswith("del_show_do|"):
        _, show_name = data.split("|", 1)
        seasons = await uploads_repo.get_show_seasons(show_name)
        for s in seasons:
            eps = await uploads_repo.get_show_episodes(show_name, s)
            for e in eps:
                path = await uploads_repo.get_episode_path(show_name, s, e)
                if path and os.path.exists(path):
                    os.remove(path)
                    remove_empty_dirs(os.path.dirname(path))
        
        await uploads_repo.delete_show(show_name)
        await q.edit_message_text(f"✅ Deleted show: {show_name}")

        if media_server_service:
            asyncio.create_task(media_server_service.trigger_scan())

    elif data.startswith("del_show_episodes|"):
        _, show_name, season_str = data.split("|", 2)
        season = int(season_str)
        eps = await uploads_repo.get_show_episodes(show_name, season)
        
        kb = [[InlineKeyboardButton(f"Delete Entire Season {season}", callback_data=f"del_season_confirm|{show_name}|{season}")]]
        for e in sorted(eps):
            kb.append([InlineKeyboardButton(f"Episode {e}", callback_data=f"del_episode_confirm|{show_name}|{season}|{e}")])
            
        await q.edit_message_text(f"Show: {show_name}\nSeason {season}\nSelect episode or delete entire season:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_season_confirm|"):
        _, show_name, season_str = data.split("|", 2)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes, Delete Season", callback_data=f"del_season_do|{show_name}|{season_str}")],
            [InlineKeyboardButton("Cancel", callback_data="del_cancel")]
        ])
        await q.edit_message_text(f"Are you sure you want to delete Season {season_str} of {show_name}?", reply_markup=kb)

    elif data.startswith("del_season_do|"):
        _, show_name, season_str = data.split("|", 2)
        season = int(season_str)
        eps = await uploads_repo.get_show_episodes(show_name, season)
        for e in eps:
            path = await uploads_repo.get_episode_path(show_name, season, e)
            if path and os.path.exists(path):
                os.remove(path)
                remove_empty_dirs(os.path.dirname(path))
                
        await uploads_repo.delete_season(show_name, season)
        await q.edit_message_text(f"✅ Deleted Season {season} of {show_name}")

        if media_server_service:
            asyncio.create_task(media_server_service.trigger_scan())

    elif data.startswith("del_episode_confirm|"):
        _, show_name, season_str, episode_str = data.split("|", 3)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes, Delete Episode", callback_data=f"del_episode_do|{show_name}|{season_str}|{episode_str}")],
            [InlineKeyboardButton("Cancel", callback_data="del_cancel")]
        ])
        await q.edit_message_text(f"Are you sure you want to delete S{int(season_str):02d}E{int(episode_str):02d} of {show_name}?", reply_markup=kb)

    elif data.startswith("del_episode_do|"):
        _, show_name, season_str, episode_str = data.split("|", 3)
        season = int(season_str)
        episode = int(episode_str)
        path = await uploads_repo.get_episode_path(show_name, season, episode)
        if path and os.path.exists(path):
            os.remove(path)
            remove_empty_dirs(os.path.dirname(path))
            
        await uploads_repo.delete_episode(show_name, season, episode)
        await q.edit_message_text(f"✅ Deleted S{season:02d}E{episode:02d} of {show_name}")

        if media_server_service:
            asyncio.create_task(media_server_service.trigger_scan())

    elif data == "del_cancel":
        await q.edit_message_text("Deletion cancelled.")
