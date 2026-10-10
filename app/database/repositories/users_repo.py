import aiosqlite


class UsersRepository:
    def __init__(self, db_conn: aiosqlite.Connection):
        self.conn = db_conn

    async def ensure_admin(self, admin_user_id: int) -> None:
        await self.conn.execute(
            """
            INSERT INTO users (id, role)
            VALUES (?, 'admin')
            ON CONFLICT(id) DO UPDATE SET role='admin';
            """,
            (admin_user_id,),
        )
        await self.conn.commit()

    async def get_user_role(self, user_id: int) -> str | None:
        async with self.conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row["role"] if row else None
