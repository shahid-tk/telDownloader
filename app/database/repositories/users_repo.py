from motor.motor_asyncio import AsyncIOMotorDatabase


class UsersRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db.users

    async def ensure_admin(self, admin_user_id: int) -> None:
        await self.col.update_one(
            {"_id": admin_user_id},
            {"$set": {"role": "admin"}},
            upsert=True,
        )