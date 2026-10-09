from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase


class UploadsRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.uploads

    async def add_movie(self, movie_name: str, filename: str, path: str) -> None:
        await self.col.insert_one(
            {
                "type": "movie",
                "movie_name": movie_name,
                "filename": filename,
                "path": path,
                "uploaded_at": datetime.utcnow(),
            }
        )

    async def get_movies(self) -> list[str]:
        cursor = self.col.find({"type": "movie"}).distinct("movie_name")
        return await cursor

    async def get_movie_path(self, movie_name: str) -> str | None:
        doc = await self.col.find_one({"type": "movie", "movie_name": movie_name})
        return doc["path"] if doc else None

    async def delete_movie(self, movie_name: str) -> None:
        await self.col.delete_one({"type": "movie", "movie_name": movie_name})

    async def get_shows(self) -> list[str]:
        cursor = self.col.find({"type": "show"}).distinct("show_name")
        return await cursor

    async def get_show_seasons(self, show_name: str) -> list[int]:
        cursor = self.col.find({"type": "show", "show_name": show_name}).distinct("season")
        return await cursor

    async def get_show_episodes(self, show_name: str, season: int) -> list[int]:
        cursor = self.col.find({"type": "show", "show_name": show_name, "season": season}).distinct("episode")
        return await cursor

    async def get_episode_path(self, show_name: str, season: int, episode: int) -> str | None:
        doc = await self.col.find_one({"type": "show", "show_name": show_name, "season": season, "episode": episode})
        return doc["path"] if doc else None

    async def delete_show(self, show_name: str) -> None:
        await self.col.delete_many({"type": "show", "show_name": show_name})

    async def delete_season(self, show_name: str, season: int) -> None:
        await self.col.delete_many({"type": "show", "show_name": show_name, "season": season})

    async def delete_episode(self, show_name: str, season: int, episode: int) -> None:
        await self.col.delete_one({"type": "show", "show_name": show_name, "season": season, "episode": episode})

    async def add_show(
        self, show_name: str, season: int, episode: int, filename: str, path: str
    ) -> None:
        await self.col.insert_one(
            {
                "type": "show",
                "show_name": show_name,
                "season": season,
                "episode": episode,
                "filename": filename,
                "path": path,
                "uploaded_at": datetime.utcnow(),
            }
        )