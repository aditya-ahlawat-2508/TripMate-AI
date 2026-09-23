from datetime import UTC, date, datetime, time

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

import graph.compose as compose_module
import graph.intake as intake_module
from graph.graph import ProviderBundle, build_plan_graph
from models import DayWeather, FlightOffer, GroundOption, Money, Place, Source, StayOffer, Trip, TripSpec


class FakeStructuredLLM:
    def __init__(self, responses):
        # Shares the list reference (no copy) so that popping persists
        # across repeated get_llm()/with_structured_output() calls within
        # the same test — e.g. the repair loop calling compose_node twice.
        self._responses = responses

    async def ainvoke(self, _messages, **_kwargs):
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


class FakeLLM:
    def __init__(self, responses):
        self._responses = responses

    def with_structured_output(self, _schema):
        return FakeStructuredLLM(self._responses)


class FakeProvider:
    def __init__(self, name, result):
        self.name = name
        self._result = result

    async def search(self, spec):
        return self._result

    async def forecast(self, spec):
        return self._result

    async def estimate(self, spec):
        return self._result


def make_place(id_, lat, lng, name="Test Place"):
    return Place(
        id=id_,
        name=name,
        category="attraction",
        lat=lat,
        lng=lng,
        source=Source(provider="fake", fetched_at=datetime.now(UTC)),
    )


@pytest.fixture
def full_spec():
    return TripSpec(
        origin="Delhi",
        destination="Goa",
        date_start=date(2026, 10, 12),
        date_end=date(2026, 10, 13),
        travelers=2,
        budget=Money(amount_minor=3000000, currency="INR"),
    )


def build_graph_with_mocks(monkeypatch, *, intake_spec, composed_plans, places):
    monkeypatch.setattr(intake_module, "get_llm", lambda: FakeLLM([intake_spec]))
    monkeypatch.setattr(compose_module, "get_composer_llm", lambda: FakeLLM(composed_plans))

    providers = ProviderBundle(
        flights=FakeProvider("fake-flights", [
            FlightOffer(
                id="f1", airline="IndiGo", dep_iata="DEL", arr_iata="GOI",
                price=Money(amount_minor=500000), source=Source(provider="fake", fetched_at=datetime.now(UTC)),
            )
        ]),
        stays=[FakeProvider("fake-stays", [
            StayOffer(id="s1", name="Beach Resort", price_per_night=Money(amount_minor=400000),
                      source=Source(provider="fake", fetched_at=datetime.now(UTC)))
        ])],
        weather=FakeProvider("fake-weather", [
            DayWeather(date=date(2026, 10, 12), temp_min_c=24, temp_max_c=31, condition="clear sky"),
            DayWeather(date=date(2026, 10, 13), temp_min_c=24, temp_max_c=31, condition="clear sky"),
        ]),
        places=FakeProvider("fake-places", places),
        ground=FakeProvider("fake-ground", [
            GroundOption(mode="cab", description="~10 hrs drive", source=Source(provider="fake", fetched_at=datetime.now(UTC)))
        ]),
    )
    return build_plan_graph(providers).compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_full_run_produces_valid_trip(monkeypatch, full_spec):
    from graph.compose import ComposedPlan, PlannedSlot

    places = [make_place("p1", 15.5, 73.8, "Baga Beach")]
    plan = ComposedPlan(slots=[
        PlannedSlot(day_index=0, start=time(10, 0), end=time(12, 0), kind="activity", title="Baga Beach", place_id="p1"),
    ])

    compiled = build_graph_with_mocks(monkeypatch, intake_spec=full_spec, composed_plans=[plan], places=places)
    config = {"configurable": {"thread_id": "t-full"}}

    result = await compiled.ainvoke({"user_query": "Goa trip", "warnings": [], "repair_count": 0}, config)

    assert "__interrupt__" not in result
    trip = result["trip"]
    assert isinstance(trip, Trip)

    # Round-trips through JSON, proving the output validates against the schema.
    reparsed = Trip.model_validate_json(trip.model_dump_json())
    assert reparsed.id == trip.id
    assert len(trip.days) == 2
    assert trip.flights[0].price.amount_minor == 500000
    assert trip.budget.total.amount_minor > 0
    assert trip.budget.fits_budget is True


@pytest.mark.asyncio
async def test_missing_fields_trigger_interrupt_then_resume(monkeypatch):
    from graph.compose import ComposedPlan

    incomplete_spec = TripSpec(destination="Goa", date_start=date(2026, 10, 12))
    compiled = build_graph_with_mocks(
        monkeypatch, intake_spec=incomplete_spec, composed_plans=[ComposedPlan(slots=[])], places=[]
    )
    config = {"configurable": {"thread_id": "t-interrupt"}}

    r1 = await compiled.ainvoke({"user_query": "Goa trip", "warnings": [], "repair_count": 0}, config)
    assert "__interrupt__" in r1
    assert r1["__interrupt__"][0].value["field"] == "origin"

    r2 = await compiled.ainvoke(Command(resume="Delhi"), config)
    assert "__interrupt__" not in r2
    assert "trip" in r2


@pytest.mark.asyncio
async def test_composer_hallucinated_place_id_is_dropped(monkeypatch, full_spec):
    from graph.compose import ComposedPlan, PlannedSlot

    plan = ComposedPlan(slots=[
        PlannedSlot(day_index=0, start=time(10, 0), end=time(11, 0), kind="activity", title="Made up place", place_id="does-not-exist"),
    ])
    compiled = build_graph_with_mocks(monkeypatch, intake_spec=full_spec, composed_plans=[plan], places=[])
    config = {"configurable": {"thread_id": "t-hallucinate"}}

    result = await compiled.ainvoke({"user_query": "Goa trip", "warnings": [], "repair_count": 0}, config)
    trip = result["trip"]
    assert all(slot.title != "Made up place" for day in trip.days for slot in day.slots)


@pytest.mark.asyncio
async def test_overloaded_day_triggers_repair_loop(monkeypatch, full_spec):
    from graph.compose import ComposedPlan, PlannedSlot

    places = [make_place("p1", 15.5, 73.8, "Baga Beach")]

    overloaded_plan = ComposedPlan(slots=[
        PlannedSlot(day_index=0, start=time(6, 0), end=time(20, 0), kind="activity", title="Marathon sightseeing", place_id="p1"),
    ])
    fixed_plan = ComposedPlan(slots=[
        PlannedSlot(day_index=0, start=time(9, 0), end=time(11, 0), kind="activity", title="Baga Beach", place_id="p1"),
    ])

    compiled = build_graph_with_mocks(
        monkeypatch, intake_spec=full_spec, composed_plans=[overloaded_plan, fixed_plan], places=places
    )
    config = {"configurable": {"thread_id": "t-repair"}}

    result = await compiled.ainvoke({"user_query": "Goa trip", "warnings": [], "repair_count": 0}, config)
    trip = result["trip"]
    titles = [slot.title for day in trip.days for slot in day.slots]
    assert "Marathon sightseeing" not in titles
    assert "Baga Beach" in titles
    assert trip.version == 2  # composed twice: original attempt + one repair


@pytest.mark.asyncio
async def test_repair_budget_exhausts_and_still_finalizes(monkeypatch, full_spec):
    """Even if every attempt keeps failing, the graph must terminate (max
    2 repairs) with a Trip carrying the leftover warnings — never loop
    forever and never crash."""

    from graph.compose import ComposedPlan, PlannedSlot

    places = [make_place("p1", 15.5, 73.8, "Baga Beach")]
    always_overloaded = ComposedPlan(slots=[
        PlannedSlot(day_index=0, start=time(6, 0), end=time(20, 0), kind="activity", title="Marathon sightseeing", place_id="p1"),
    ])

    compiled = build_graph_with_mocks(
        monkeypatch, intake_spec=full_spec, composed_plans=[always_overloaded], places=places
    )
    config = {"configurable": {"thread_id": "t-exhaust"}, "recursion_limit": 50}

    result = await compiled.ainvoke({"user_query": "Goa trip", "warnings": [], "repair_count": 0}, config)
    trip = result["trip"]
    assert isinstance(trip, Trip)
    assert any("comfort limit" in w for w in trip.warnings)


@pytest.mark.asyncio
async def test_provider_failure_produces_warning_not_crash(monkeypatch, full_spec):
    from graph.compose import ComposedPlan

    class FailingProvider:
        name = "failing"

        async def search(self, spec):
            raise RuntimeError("simulated provider outage")

    monkeypatch.setattr(intake_module, "get_llm", lambda: FakeLLM([full_spec]))
    monkeypatch.setattr(compose_module, "get_composer_llm", lambda: FakeLLM([ComposedPlan(slots=[])]))

    providers = ProviderBundle(
        flights=FailingProvider(),
        stays=[FailingProvider()],
        weather=FakeProvider("fake-weather", []),
        places=FakeProvider("fake-places", []),
        ground=FakeProvider("fake-ground", []),
    )
    compiled = build_plan_graph(providers).compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t-fail"}}

    result = await compiled.ainvoke({"user_query": "Goa trip", "warnings": [], "repair_count": 0}, config)
    trip = result["trip"]
    assert isinstance(trip, Trip)
    assert any("live flight" in w.lower() or "outage" in w.lower() for w in result["warnings"])
