from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class Mongo:
    def __init__(self, uri: str):
        self.client = AsyncIOMotorClient(uri)
        db_name = uri.rsplit("/", 1)[-1] if "/" in uri else "media_ingestion"
        self.db: AsyncIOMotorDatabase = self.client[db_name]

    async def ensure_indexes(self) -> None:
        # _id is already unique by default in MongoDB
        await self.db.sessions.create_index("chat_id", unique=True)
        await self.db.sessions.create_index("updated_at")
        await self.db.uploads.create_index("uploaded_at")
        await self.db.uploads.create_index("path", unique=True)

    async def close(self) -> None:
        self.client.close()
