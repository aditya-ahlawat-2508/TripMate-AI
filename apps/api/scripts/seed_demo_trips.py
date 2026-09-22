"""Seeds 2-3 pre-generated showcase trips (docs/blueprint.md's "demo mode",
§ Demo mode — required before the LinkedIn post): servable from the
database with zero LLM/API cost, for a "Try a sample trip" landing-page
button and for visitors who hit a rate limit.

These are hand-built, not composed live by the graph (no working LLM key
was available to run the real pipeline end-to-end when this was written).
Every Source on a priced item is explicitly labeled provider="demo-seed"
rather than a real provider name — these are believable placeholder
numbers for demo purposes, never claimed as live prices. Place
coordinates are real.

Run from apps/api/: python -m scripts.seed_demo_trips
"""

import asyncio
import uuid
from datetime import UTC, date, datetime, time

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from backend import get_database_url
from models import BudgetBreakdown, Day, DayWeather, Money, Slot, Source, Trip, TripSpec
from trips_store import ensure_trips_table, save_trip

DEMO_SOURCE = lambda: Source(provider="demo-seed", fetched_at=datetime.now(UTC))  # noqa: E731


def goa_trip() -> Trip:
    spec = TripSpec(
        origin="Delhi",
        destination="Goa",
        date_start=date(2026, 10, 12),
        date_end=date(2026, 10, 13),
        travelers=2,
        budget=Money(amount_minor=3000000, currency="INR"),
        pace="balanced",
        interests=["beaches", "nightlife"],
    )

    days = [
        Day(
            date=date(2026, 10, 12),
            weather=DayWeather(date=date(2026, 10, 12), temp_min_c=24, temp_max_c=32, condition="mainly clear"),
            slots=[
                Slot(start=time(9, 0), end=time(11, 0), kind="activity", title="Baga Beach", lat=15.5553, lng=73.7517, source=DEMO_SOURCE()),
                Slot(start=time(13, 0), end=time(14, 0), kind="meal", title="Lunch at Candolim", lat=15.5183, lng=73.7629, source=DEMO_SOURCE()),
                Slot(start=time(16, 0), end=time(17, 30), kind="activity", title="Fort Aguada", lat=15.4925, lng=73.7734, cost=Money(amount_minor=0), source=DEMO_SOURCE()),
                Slot(start=time(20, 0), end=time(22, 0), kind="meal", title="Dinner in Anjuna", lat=15.5847, lng=73.7404, source=DEMO_SOURCE()),
            ],
        ),
        Day(
            date=date(2026, 10, 13),
            weather=DayWeather(date=date(2026, 10, 13), temp_min_c=24, temp_max_c=31, condition="partly cloudy"),
            slots=[
                Slot(start=time(10, 0), end=time(12, 0), kind="activity", title="Chapora Fort", lat=15.6047, lng=73.7358, cost=Money(amount_minor=0), source=DEMO_SOURCE()),
                Slot(start=time(14, 0), end=time(15, 0), kind="meal", title="Lunch in Vagator", lat=15.5977, lng=73.7396, source=DEMO_SOURCE()),
            ],
        ),
    ]
    days[0].slots.insert(0, Slot(
        start=time(6, 0), end=time(8, 0), kind="transit", title="Flight: IndiGo DEL->GOI",
        cost=Money(amount_minor=560000), source=DEMO_SOURCE(),
    ))
    for day in days:
        day.slots.append(Slot(
            start=time(21, 0), end=time(23, 59), kind="stay", title="Stay: Baga Beach Resort",
            lat=15.555, lng=73.751, cost=Money(amount_minor=480000), source=DEMO_SOURCE(),
        ))

    total_minor = sum(s.cost.amount_minor for day in days for s in day.slots if s.cost)
    budget = BudgetBreakdown(
        total=Money(amount_minor=total_minor),
        limit=spec.budget,
        by_category={"transit": Money(amount_minor=560000), "stay": Money(amount_minor=960000)},
        fits_budget=total_minor <= spec.budget.amount_minor,
    )

    return Trip(id=uuid.uuid4(), spec=spec, days=days, budget=budget, warnings=[], version=1)


def manali_trip() -> Trip:
    spec = TripSpec(
        origin="Delhi",
        destination="Manali",
        date_start=date(2026, 12, 20),
        date_end=date(2026, 12, 21),
        travelers=2,
        budget=Money(amount_minor=1500000, currency="INR"),
        pace="relaxed",
        interests=["mountains", "snow"],
    )

    days = [
        Day(
            date=date(2026, 12, 20),
            weather=DayWeather(date=date(2026, 12, 20), temp_min_c=-2, temp_max_c=8, condition="light snow"),
            slots=[
                Slot(start=time(10, 0), end=time(12, 0), kind="activity", title="Hidimba Devi Temple", lat=32.2461, lng=77.1892, cost=Money(amount_minor=0), source=DEMO_SOURCE()),
                Slot(start=time(13, 0), end=time(14, 0), kind="meal", title="Lunch on Mall Road", lat=32.2396, lng=77.1887, source=DEMO_SOURCE()),
                Slot(start=time(15, 0), end=time(17, 0), kind="activity", title="Old Manali walk", lat=32.2545, lng=77.1739, cost=Money(amount_minor=0), source=DEMO_SOURCE()),
            ],
        ),
        Day(
            date=date(2026, 12, 21),
            weather=DayWeather(date=date(2026, 12, 21), temp_min_c=-3, temp_max_c=6, condition="overcast"),
            slots=[
                Slot(start=time(9, 0), end=time(15, 0), kind="activity", title="Solang Valley", lat=32.3181, lng=77.1567, cost=Money(amount_minor=150000), source=DEMO_SOURCE()),
            ],
        ),
    ]
    for day in days:
        day.slots.append(Slot(
            start=time(20, 0), end=time(23, 59), kind="stay", title="Stay: Old Manali Guesthouse",
            lat=32.2545, lng=77.1739, cost=Money(amount_minor=220000), source=DEMO_SOURCE(),
        ))

    total_minor = sum(s.cost.amount_minor for day in days for s in day.slots if s.cost)
    budget = BudgetBreakdown(
        total=Money(amount_minor=total_minor),
        limit=spec.budget,
        by_category={"activity": Money(amount_minor=150000), "stay": Money(amount_minor=440000)},
        fits_budget=total_minor <= spec.budget.amount_minor,
    )

    return Trip(id=uuid.uuid4(), spec=spec, days=days, budget=budget, warnings=[], version=1)


async def main():
    pool = AsyncConnectionPool(get_database_url(), open=False, kwargs={"autocommit": True, "row_factory": dict_row})
    await pool.open()
    await ensure_trips_table(pool)

    for trip in (goa_trip(), manali_trip()):
        await save_trip(pool, trip, thread_id=f"demo-{trip.spec.destination.lower()}", is_demo=True)
        print(f"Seeded demo trip: {trip.spec.destination} ({trip.id})")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
