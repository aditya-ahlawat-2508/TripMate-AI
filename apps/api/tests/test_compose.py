from datetime import UTC, date, datetime, time

from graph.compose import _compute_budget, _parse_time
from models import Day, Money, Slot, Source, TripSpec


def make_source():
    return Source(provider="fake", fetched_at=datetime.now(UTC))


def test_compute_budget_sums_matching_currency():
    day = Day(date=date(2026, 10, 12), slots=[
        Slot(start=time(6, 0), end=time(9, 0), kind="transit", title="Flight", cost=Money(amount_minor=500000, currency="INR"), source=make_source()),
        Slot(start=time(20, 0), end=time(23, 0), kind="stay", title="Hotel", cost=Money(amount_minor=400000, currency="INR"), source=make_source()),
    ])
    spec = TripSpec(origin="Delhi", destination="Goa", budget=Money(amount_minor=3000000, currency="INR"))

    budget, warnings = _compute_budget([day], spec)

    assert budget.total.amount_minor == 900000
    assert budget.total.currency == "INR"
    assert budget.fits_budget is True
    assert warnings == []


def test_compute_budget_excludes_mismatched_currency_with_warning():
    # Real bug found live-testing Duffel's sandbox: it returns fares in EUR
    # regardless of route, while the trip's own budget is in INR. Summing
    # amount_minor across currencies would silently produce a meaningless
    # total — this must never happen.
    day = Day(date=date(2026, 10, 12), slots=[
        Slot(start=time(6, 0), end=time(9, 0), kind="transit", title="Flight", cost=Money(amount_minor=23655, currency="EUR"), source=make_source()),
        Slot(start=time(20, 0), end=time(23, 0), kind="stay", title="Hotel", cost=Money(amount_minor=400000, currency="INR"), source=make_source()),
    ])
    spec = TripSpec(origin="Delhi", destination="Goa", budget=Money(amount_minor=3000000, currency="INR"))

    budget, warnings = _compute_budget([day], spec)

    assert budget.total.amount_minor == 400000  # only the INR stay, not the EUR flight
    assert budget.total.currency == "INR"
    assert len(warnings) == 1
    assert "EUR" in warnings[0]
    assert "Flight" in warnings[0]
    assert "stay" in budget.by_category
    assert "transit" not in budget.by_category


def test_compute_budget_no_spec_budget_defaults_to_inr():
    day = Day(date=date(2026, 10, 12), slots=[])
    spec = TripSpec(origin="Delhi", destination="Goa")

    budget, warnings = _compute_budget([day], spec)

    assert budget.total.currency == "INR"
    assert budget.fits_budget is None
    assert warnings == []


def test_compute_budget_deduplicates_repeated_warnings():
    day = Day(date=date(2026, 10, 12), slots=[
        Slot(start=time(9, 0), end=time(10, 0), kind="stay", title="Hotel", cost=Money(amount_minor=100, currency="EUR"), source=make_source()),
    ])
    day2 = Day(date=date(2026, 10, 13), slots=[
        Slot(start=time(9, 0), end=time(10, 0), kind="stay", title="Hotel", cost=Money(amount_minor=100, currency="EUR"), source=make_source()),
    ])
    spec = TripSpec(origin="Delhi", destination="Goa", budget=Money(amount_minor=3000000, currency="INR"))

    _, warnings = _compute_budget([day, day2], spec)
    assert len(warnings) == 1


def test_parse_time_accepts_hh_mm_ss():
    assert _parse_time("08:30:00", fallback=time(0, 0)) == time(8, 30)


def test_parse_time_accepts_hh_mm():
    # The real bug: Groq's tool-schema validator wanted HH:MM:SS and
    # rejected the HH:MM the model actually produces, failing every
    # composer call. start/end are parsed leniently instead of trusting
    # the model's exact format.
    assert _parse_time("08:30", fallback=time(0, 0)) == time(8, 30)


def test_parse_time_falls_back_on_garbage():
    assert _parse_time("not a time", fallback=time(9, 0)) == time(9, 0)


def test_parse_time_strips_whitespace():
    assert _parse_time("  08:30  ", fallback=time(0, 0)) == time(8, 30)
