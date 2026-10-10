from datetime import datetime
from typing import Optional
import aiosqlite


class UploadsRepository:
    def __init__(self, db_conn: aiosqlite.Connection):
        self.conn = db_conn

    async def add_movie(self, movie_name: str, filename: str, path: str) -> None:
        now = datetime.utcnow().isoformat()
        await self.conn.execute(
            """
            INSERT INTO uploads (type, movie_name, filename, path, uploaded_at)
            VALUES ('movie', ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                movie_name = excluded.movie_name,
                filename = excluded.filename,
                uploaded_at = excluded.uploaded_at;
            """,
            (movie_name, filename, path, now),
        )
        await self.conn.commit()

    async def get_movies(self) -> list[str]:
        async with self.conn.execute(
            "SELECT DISTINCT movie_name FROM uploads WHERE type = 'movie' AND movie_name IS NOT NULL ORDER BY movie_name ASC"
        ) as cur:
            rows = await cur.fetchall()
            return [row["movie_name"] for row in rows]

    async def get_movie_path(self, movie_name: str) -> str | None:
        async with self.conn.execute(
            "SELECT path FROM uploads WHERE type = 'movie' AND movie_name = ? LIMIT 1",
            (movie_name,),
        ) as cur:
            row = await cur.fetchone()
            return row["path"] if row else None

    async def delete_movie(self, movie_name: str) -> None:
        await self.conn.execute(
            "DELETE FROM uploads WHERE type = 'movie' AND movie_name = ?",
            (movie_name,),
        )
        await self.conn.commit()

    async def get_shows(self) -> list[str]:
        async with self.conn.execute(
            "SELECT DISTINCT show_name FROM uploads WHERE type = 'show' AND show_name IS NOT NULL ORDER BY show_name ASC"
        ) as cur:
            rows = await cur.fetchall()
            return [row["show_name"] for row in rows]

    async def get_show_seasons(self, show_name: str) -> list[int]:
        async with self.conn.execute(
            "SELECT DISTINCT season FROM uploads WHERE type = 'show' AND show_name = ? AND season IS NOT NULL ORDER BY season ASC",
            (show_name,),
        ) as cur:
            rows = await cur.fetchall()
            return [int(row["season"]) for row in rows]

    async def get_show_episodes(self, show_name: str, season: int) -> list[int]:
        async with self.conn.execute(
            "SELECT DISTINCT episode FROM uploads WHERE type = 'show' AND show_name = ? AND season = ? AND episode IS NOT NULL ORDER BY episode ASC",
            (show_name, season),
        ) as cur:
            rows = await cur.fetchall()
            return [int(row["episode"]) for row in rows]

    async def get_episode_path(self, show_name: str, season: int, episode: int) -> str | None:
        async with self.conn.execute(
            "SELECT path FROM uploads WHERE type = 'show' AND show_name = ? AND season = ? AND episode = ? LIMIT 1",
            (show_name, season, episode),
        ) as cur:
            row = await cur.fetchone()
            return row["path"] if row else None

    async def delete_show(self, show_name: str) -> None:
        await self.conn.execute(
            "DELETE FROM uploads WHERE type = 'show' AND show_name = ?",
            (show_name,),
        )
        await self.conn.commit()

    async def delete_season(self, show_name: str, season: int) -> None:
        await self.conn.execute(
            "DELETE FROM uploads WHERE type = 'show' AND show_name = ? AND season = ?",
            (show_name, season),
        )
        await self.conn.commit()

    async def delete_episode(self, show_name: str, season: int, episode: int) -> None:
        await self.conn.execute(
            "DELETE FROM uploads WHERE type = 'show' AND show_name = ? AND season = ? AND episode = ?",
            (show_name, season, episode),
        )
        await self.conn.commit()

    async def add_show(
        self, show_name: str, season: int, episode: int, filename: str, path: str
    ) -> None:
        now = datetime.utcnow().isoformat()
        await self.conn.execute(
            """
            INSERT INTO uploads (type, show_name, season, episode, filename, path, uploaded_at)
            VALUES ('show', ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                show_name = excluded.show_name,
                season = excluded.season,
                episode = excluded.episode,
                filename = excluded.filename,
                uploaded_at = excluded.uploaded_at;
            """,
            (show_name, season, episode, filename, path, now),
        )
        await self.conn.commit()

    async def get_recent_uploads(self, limit: int = 50) -> list[dict]:
        async with self.conn.execute(
            "SELECT * FROM uploads ORDER BY uploaded_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
