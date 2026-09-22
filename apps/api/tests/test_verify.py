from datetime import UTC, date, datetime, time

from graph.verify import (
    MAX_DAILY_ACTIVITY_HOURS,
    MAX_PLACE_DISTANCE_KM,
    _check_daily_hours,
    _check_geography,
    _check_sourced_prices,
    _haversine_km,
)
from models import BudgetBreakdown, Day, Money, Place, Slot, Source, Trip, TripSpec


def make_trip(days):
    return Trip(
        id="00000000-0000-0000-0000-000000000000",
        spec=TripSpec(origin="Delhi", destination="Goa"),
        days=days,
        budget=BudgetBreakdown(total=Money(amount_minor=0)),
    )


def make_place(id_, lat, lng):
    return Place(
        id=id_, name=id_, category="attraction", lat=lat, lng=lng,
        source=Source(provider="fake", fetched_at=datetime.now(UTC)),
    )


def test_haversine_known_distance():
    # Delhi to Mumbai is roughly 1150km as the crow flies.
    d = _haversine_km(28.6139, 77.2090, 19.0760, 72.8777)
    assert 1100 < d < 1200


def test_check_daily_hours_flags_overload():
    day = Day(date=date(2026, 10, 12), slots=[
        Slot(start=time(6, 0), end=time(20, 0), kind="activity", title="Marathon day"),
    ])
    issues = _check_daily_hours(make_trip([day]))
    assert len(issues) == 1
    assert "comfort limit" in issues[0]


def test_check_daily_hours_ok_under_limit():
    day = Day(date=date(2026, 10, 12), slots=[
        Slot(start=time(9, 0), end=time(11, 0), kind="activity", title="Museum"),
        Slot(start=time(13, 0), end=time(14, 0), kind="meal", title="Lunch"),
    ])
    assert _check_daily_hours(make_trip([day])) == []


def test_check_daily_hours_ignores_stay_and_transit():
    day = Day(date=date(2026, 10, 12), slots=[
        Slot(start=time(0, 0), end=time(23, 59), kind="stay", title="Hotel"),
    ])
    assert _check_daily_hours(make_trip([day])) == []


def test_check_sourced_prices_drops_unsourced_cost():
    slot = Slot(start=time(9, 0), end=time(10, 0), kind="activity", title="Mystery paid thing", cost=Money(amount_minor=100), source=None)
    day = Day(date=date(2026, 10, 12), slots=[slot])
    issues = _check_sourced_prices(make_trip([day]))
    assert len(issues) == 1
    assert slot.cost is None  # the check mutates the slot to remove the unsourced price


def test_check_sourced_prices_allows_sourced_cost():
    source = Source(provider="fake", fetched_at=datetime.now(UTC))
    slot = Slot(start=time(9, 0), end=time(10, 0), kind="stay", title="Hotel", cost=Money(amount_minor=100), source=source)
    day = Day(date=date(2026, 10, 12), slots=[slot])
    assert _check_sourced_prices(make_trip([day])) == []
    assert slot.cost is not None


def test_check_geography_flags_far_place():
    places = [make_place("p1", 15.5, 73.8)]  # Goa-ish
    far_slot = Slot(start=time(9, 0), end=time(10, 0), kind="activity", title="Red Fort", lat=28.6139, lng=77.2090)
    day = Day(date=date(2026, 10, 12), slots=[far_slot])
    issues = _check_geography(make_trip([day]), places)
    assert len(issues) == 1
    assert "wrong city" in issues[0]


def test_check_geography_allows_nearby_place():
    places = [make_place("p1", 15.5, 73.8)]
    near_slot = Slot(start=time(9, 0), end=time(10, 0), kind="activity", title="Baga Beach", lat=15.55, lng=73.75)
    day = Day(date=date(2026, 10, 12), slots=[near_slot])
    assert _check_geography(make_trip([day]), places) == []


def test_check_geography_skips_slots_without_coordinates():
    day = Day(date=date(2026, 10, 12), slots=[Slot(start=time(9, 0), end=time(10, 0), kind="meal", title="Lunch")])
    assert _check_geography(make_trip([day]), [make_place("p1", 15.5, 73.8)]) == []


def test_constants_are_sane():
    assert MAX_DAILY_ACTIVITY_HOURS > 0
    assert MAX_PLACE_DISTANCE_KM > 0
