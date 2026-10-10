from database.repositories.sessions_repo import SessionsRepository


class SessionService:
    def __init__(self, repo: SessionsRepository):
        self.repo = repo

    async def get(self, chat_id: int):
        return await self.repo.get(chat_id)

    async def create_movie_session(self, chat_id: int, movie_name: str):
        await self.repo.upsert(
            chat_id,
            {
                "chat_id": chat_id,
                "mode": "movie",
                "movie_name": movie_name,
                "status": "waiting_file",
            },
        )

    async def create_show_session(self, chat_id: int, show_name: str, season: int, next_episode: int = 1):
        await self.repo.upsert(
            chat_id,
            {
                "chat_id": chat_id,
                "mode": "show",
                "show_name": show_name,
                "season": season,
                "next_episode": next_episode,
                "episodes_uploaded": 0,
                "status": "uploading",
            },
        )

    async def delete(self, chat_id: int):
        await self.repo.delete(chat_id)

    async def increment_episode(self, chat_id: int):
        await self.repo.increment_episode(chat_id)

    async def update_episode_progress(self, chat_id: int, count: int, next_ep: int):
        await self.repo.update_episode_progress(chat_id, count, next_ep)
