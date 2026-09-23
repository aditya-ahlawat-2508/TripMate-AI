"""Entitlements (docs/blueprint.md §08 Data model: `subscriptions`).
One row per owner_id; a webhook flips status to "active" once Razorpay
confirms payment. No trial/grace-period logic yet — status is just
"none" | "active" | "cancelled".
"""

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS subscriptions (
    owner_id TEXT PRIMARY KEY,
    plan TEXT NOT NULL DEFAULT 'free',
    status TEXT NOT NULL DEFAULT 'none',
    razorpay_order_id TEXT,
    razorpay_payment_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


async def ensure_subscriptions_table(pool) -> None:
    async with pool.connection() as conn:
        await conn.execute(CREATE_TABLE_SQL)


async def record_pending_order(pool, owner_id: str, order_id: str) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO subscriptions (owner_id, plan, status, razorpay_order_id, updated_at)
            VALUES (%s, 'pro', 'pending', %s, now())
            ON CONFLICT (owner_id) DO UPDATE
                SET razorpay_order_id = EXCLUDED.razorpay_order_id, status = 'pending', updated_at = now()
            """,
            (owner_id, order_id),
        )


async def activate_subscription(pool, order_id: str, payment_id: str) -> str | None:
    """Called from the webhook once Razorpay confirms payment. Returns the
    owner_id that got activated, or None if no pending order matched
    (e.g. a replayed/unknown webhook — logged by the caller, not raised)."""

    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            UPDATE subscriptions
            SET status = 'active', razorpay_payment_id = %s, updated_at = now()
            WHERE razorpay_order_id = %s
            RETURNING owner_id
            """,
            (payment_id, order_id),
        )
        row = await cur.fetchone()

    if not row:
        return None
    return row["owner_id"] if isinstance(row, dict) else row[0]


async def get_subscription_status(pool, owner_id: str) -> dict:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT plan, status FROM subscriptions WHERE owner_id = %s",
            (owner_id,),
        )
        row = await cur.fetchone()

    if not row:
        return {"plan": "free", "status": "none"}
    if isinstance(row, dict):
        return {"plan": row["plan"], "status": row["status"]}
    return {"plan": row[0], "status": row[1]}
