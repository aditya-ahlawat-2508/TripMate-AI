from datetime import date

from models import Money, TripSpec


def test_none_interests_and_constraints_normalize_to_empty_list():
    # Real bug found live-testing against Groq: the model emits null for
    # "nothing to put here" instead of [], and a bare list[str] schema
    # rejects null at the tool-call validation layer, failing every
    # intake call with no stated interests/constraints.
    spec = TripSpec.model_validate({"origin": "Delhi", "destination": "Goa", "interests": None, "constraints": None})
    assert spec.interests == []
    assert spec.constraints == []


def test_missing_interests_and_constraints_default_to_empty_list():
    spec = TripSpec(origin="Delhi", destination="Goa")
    assert spec.interests == []
    assert spec.constraints == []


def test_real_interests_pass_through():
    spec = TripSpec.model_validate({"origin": "Delhi", "destination": "Goa", "interests": ["beaches", "food"]})
    assert spec.interests == ["beaches", "food"]


def test_json_schema_allows_null_for_interests_and_constraints():
    schema = TripSpec.model_json_schema()
    for field in ("interests", "constraints"):
        types = [option.get("type") for option in schema["properties"][field]["anyOf"]]
        assert "null" in types
        assert "array" in types


def test_missing_required_fields():
    assert TripSpec().missing_required_fields() == ["origin", "destination", "date_start"]
    assert TripSpec(origin="Delhi").missing_required_fields() == ["destination", "date_start"]
    assert TripSpec(origin="Delhi", suggest_destination=True, flexible_dates=True).missing_required_fields() == []


def test_trip_length_days_computes_inclusive_span():
    spec = TripSpec(date_start=date(2026, 11, 15), date_end=date(2026, 11, 16))
    assert spec.trip_length_days() == 2


def test_trip_length_days_defaults_to_one_without_dates():
    assert TripSpec().trip_length_days() == 1


def test_budget_roundtrips():
    spec = TripSpec(budget=Money(amount_minor=3000000, currency="INR"))
    assert spec.budget.amount == 30000.0
