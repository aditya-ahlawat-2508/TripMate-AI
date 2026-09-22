import uuid

from models import BudgetBreakdown, Money, Trip, TripSpec
from trips_store import _parse_trip


def make_trip() -> Trip:
    return Trip(
        id=uuid.uuid4(),
        spec=TripSpec(origin="Delhi", destination="Goa"),
        budget=BudgetBreakdown(total=Money(amount_minor=0)),
    )


def test_parse_trip_from_dict():
    # This is what psycopg's dict_row row_factory actually hands back for
    # a jsonb column — already-decoded Python objects, not a JSON string.
    trip = make_trip()
    parsed = _parse_trip(trip.model_dump(mode="json"))
    assert parsed.id == trip.id
    assert parsed.spec.destination == "Goa"


def test_parse_trip_from_json_string():
    trip = make_trip()
    parsed = _parse_trip(trip.model_dump_json())
    assert parsed.id == trip.id
