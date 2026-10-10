from datetime import datetime
from typing import Optional
import aiosqlite


class SessionsRepository:
    def __init__(self, db_conn: aiosqlite.Connection):
        self.conn = db_conn

    async def get(self, chat_id: int) -> Optional[dict]:
        async with self.conn.execute("SELECT * FROM sessions WHERE chat_id = ?", (chat_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return dict(row)

    async def upsert(self, chat_id: int, data: dict) -> None:
        now = datetime.utcnow().isoformat()
        mode = data.get("mode", "")
        movie_name = data.get("movie_name")
        show_name = data.get("show_name")
        season = data.get("season")
        next_episode = data.get("next_episode", 1)
        episodes_uploaded = data.get("episodes_uploaded", 0)
        status = data.get("status")

        await self.conn.execute(
            """
            INSERT INTO sessions (
                chat_id, mode, movie_name, show_name, season, next_episode, episodes_uploaded, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                mode = excluded.mode,
                movie_name = excluded.movie_name,
                show_name = excluded.show_name,
                season = excluded.season,
                next_episode = excluded.next_episode,
                episodes_uploaded = excluded.episodes_uploaded,
                status = excluded.status,
                updated_at = excluded.updated_at;
            """,
            (
                chat_id,
                mode,
                movie_name,
                show_name,
                season,
                next_episode,
                episodes_uploaded,
                status,
                now,
            ),
        )
        await self.conn.commit()

    async def delete(self, chat_id: int) -> None:
        await self.conn.execute("DELETE FROM sessions WHERE chat_id = ?", (chat_id,))
        await self.conn.commit()

    async def increment_episode(self, chat_id: int) -> None:
        now = datetime.utcnow().isoformat()
        await self.conn.execute(
            """
            UPDATE sessions
            SET next_episode = next_episode + 1,
                episodes_uploaded = episodes_uploaded + 1,
                updated_at = ?
            WHERE chat_id = ?;
            """,
            (now, chat_id),
        )
        await self.conn.commit()

    async def update_episode_progress(self, chat_id: int, count: int, next_ep: int) -> None:
        now = datetime.utcnow().isoformat()
        await self.conn.execute(
            """
            UPDATE sessions
            SET episodes_uploaded = episodes_uploaded + ?,
                next_episode = ?,
                updated_at = ?
            WHERE chat_id = ?;
            """,
            (count, next_ep, now, chat_id),
        )
        await self.conn.commit()
