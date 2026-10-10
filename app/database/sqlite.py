import aiosqlite
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA synchronous=NORMAL;")
        await self.ensure_tables()

    async def ensure_tables(self) -> None:
        async with self._conn.cursor() as cur:
            # Users table
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    role TEXT NOT NULL DEFAULT 'user'
                );
                """
            )

            # Sessions table
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    chat_id INTEGER PRIMARY KEY,
                    mode TEXT NOT NULL,
                    movie_name TEXT,
                    show_name TEXT,
                    season INTEGER,
                    next_episode INTEGER DEFAULT 1,
                    episodes_uploaded INTEGER DEFAULT 0,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # Uploads table
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    movie_name TEXT,
                    show_name TEXT,
                    season INTEGER,
                    episode INTEGER,
                    filename TEXT NOT NULL,
                    path TEXT UNIQUE NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # Indices
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_uploads_type ON uploads(type);")
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_uploads_show ON uploads(show_name, season);")
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_uploads_movie ON uploads(movie_name);")
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_uploads_uploaded_at ON uploads(uploaded_at);")

            await self._conn.commit()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._conn

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("SQLite connection closed.")


# Global persistent database instance
db = None


async def get_db(db_path: str) -> Database:
    global db
    if db is None:
        db = Database(db_path)
        await db.connect()
    return db
