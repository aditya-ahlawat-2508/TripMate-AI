"""Minimal trip persistence — no user accounts yet (that's Clerk, Phase 5,
blocked on the owner creating an account), but trip IDs are always
server-generated UUIDs from Trip.id, never a client-supplied string. This
directly narrows the old thread_id IDOR issue: an ID can't be chosen or
guessed the way an arbitrary thread_id could, even though there's still no
per-user ownership check until auth exists.
"""

from uuid import UUID

from models import Trip

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trips (
    id UUID PRIMARY KEY,
    thread_id TEXT NOT NULL,
    trip JSONB NOT NULL,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


async def ensure_trips_table(pool) -> None:
    async with pool.connection() as conn:
        await conn.execute(CREATE_TABLE_SQL)


async def save_trip(pool, trip: Trip, thread_id: str, is_demo: bool = False) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO trips (id, thread_id, trip, is_demo)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET trip = EXCLUDED.trip
            """,
            (str(trip.id), thread_id, trip.model_dump_json(), is_demo),
        )


async def get_trip(pool, trip_id: str) -> Trip | None:
    try:
        UUID(trip_id)
    except ValueError:
        return None

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT trip FROM trips WHERE id = %s", (trip_id,))
        row = await cur.fetchone()

    if not row:
        return None
    return _parse_trip(row["trip"] if isinstance(row, dict) else row[0])


async def list_demo_trips(pool) -> list[Trip]:
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT trip FROM trips WHERE is_demo = TRUE ORDER BY created_at")
        rows = await cur.fetchall()

    return [_parse_trip(row["trip"] if isinstance(row, dict) else row[0]) for row in rows]


def _parse_trip(value) -> Trip:
    # psycopg's dict_row row_factory auto-decodes jsonb columns into a
    # Python dict already — only fall back to JSON-string parsing if it
    # ever comes back as a string (e.g. a different row_factory).
    if isinstance(value, str):
        return Trip.model_validate_json(value)
    return Trip.model_validate(value)
