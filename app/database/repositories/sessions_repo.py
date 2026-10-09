from datetime import datetime
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase


class SessionsRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.sessions

    async def get(self, chat_id: int) -> Optional[dict]:
        return await self.col.find_one({"chat_id": chat_id})

    async def upsert(self, chat_id: int, data: dict) -> None:
        now = datetime.utcnow()
        data["updated_at"] = now
        await self.col.update_one(
            {"chat_id": chat_id},
            {"$set": data, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    async def delete(self, chat_id: int) -> None:
        await self.col.delete_one({"chat_id": chat_id})

    async def increment_episode(self, chat_id: int) -> None:
        await self.col.update_one(
            {"chat_id": chat_id},
            {
                "$inc": {"next_episode": 1, "episodes_uploaded": 1},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )

    async def update_episode_progress(self, chat_id: int, count: int, next_ep: int) -> None:
        await self.col.update_one(
            {"chat_id": chat_id},
            {
                "$inc": {"episodes_uploaded": count},
                "$set": {"next_episode": next_ep, "updated_at": datetime.utcnow()},
            },
        )
