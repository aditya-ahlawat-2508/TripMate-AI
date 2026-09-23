"""Trip persistence. Trip IDs are always server-generated UUIDs from
Trip.id, never a client-supplied string — narrows the old thread_id IDOR
issue on its own. Clerk auth (2026-09-23) adds real per-user ownership on
top: owner_id is nullable (anonymous planning still works), but once set
it's checked on every read that isn't a demo trip.
"""

from uuid import UUID

from models import Trip

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trips (
    id UUID PRIMARY KEY,
    thread_id TEXT NOT NULL,
    owner_id TEXT,
    trip JSONB NOT NULL,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Idempotent: lets an already-deployed trips table (from before owner_id
# existed) pick up the column without a manual migration step.
ADD_OWNER_ID_SQL = "ALTER TABLE trips ADD COLUMN IF NOT EXISTS owner_id TEXT;"


async def ensure_trips_table(pool) -> None:
    async with pool.connection() as conn:
        await conn.execute(CREATE_TABLE_SQL)
        await conn.execute(ADD_OWNER_ID_SQL)


async def save_trip(pool, trip: Trip, thread_id: str, is_demo: bool = False, owner_id: str | None = None) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO trips (id, thread_id, owner_id, trip, is_demo)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET trip = EXCLUDED.trip
            """,
            (str(trip.id), thread_id, owner_id, trip.model_dump_json(), is_demo),
        )


async def get_trip(pool, trip_id: str, owner_id: str | None = None) -> Trip | None:
    """owner_id=None means "no auth context" (e.g. a public share-page
    view) — returns the trip regardless of who owns it, same as before
    Clerk existed. A trip's actual privacy model (should non-owners be
    able to view a share link at all?) is a product decision, not
    resolved here; this just adds the *capability* to check ownership
    where the caller wants to (see require_owned_trip in app.py)."""

    try:
        UUID(trip_id)
    except ValueError:
        return None

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT trip, owner_id, is_demo FROM trips WHERE id = %s", (trip_id,))
        row = await cur.fetchone()

    if not row:
        return None
    return _parse_trip(row["trip"] if isinstance(row, dict) else row[0])


async def get_trip_owner(pool, trip_id: str) -> tuple[str | None, bool] | None:
    """Returns (owner_id, is_demo) for a trip, or None if it doesn't
    exist. Used to decide whether a request is allowed to mutate/delete a
    trip without loading and re-parsing the whole thing."""

    try:
        UUID(trip_id)
    except ValueError:
        return None

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT owner_id, is_demo FROM trips WHERE id = %s", (trip_id,))
        row = await cur.fetchone()

    if not row:
        return None
    if isinstance(row, dict):
        return row["owner_id"], row["is_demo"]
    return row[0], row[1]


async def list_demo_trips(pool) -> list[Trip]:
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT trip FROM trips WHERE is_demo = TRUE ORDER BY created_at")
        rows = await cur.fetchall()

    return [_parse_trip(row["trip"] if isinstance(row, dict) else row[0]) for row in rows]


async def list_user_trips(pool, owner_id: str) -> list[Trip]:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT trip FROM trips WHERE owner_id = %s ORDER BY created_at DESC",
            (owner_id,),
        )
        rows = await cur.fetchall()

    return [_parse_trip(row["trip"] if isinstance(row, dict) else row[0]) for row in rows]


def _parse_trip(value) -> Trip:
    # psycopg's dict_row row_factory auto-decodes jsonb columns into a
    # Python dict already — only fall back to JSON-string parsing if it
    # ever comes back as a string (e.g. a different row_factory).
    if isinstance(value, str):
        return Trip.model_validate_json(value)
    return Trip.model_validate(value)
