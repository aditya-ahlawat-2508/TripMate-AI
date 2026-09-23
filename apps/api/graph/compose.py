import logging
import uuid
from datetime import date, datetime, time, timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from models import BudgetBreakdown, Day, Money, Slot, Trip
from observability import get_langfuse_callbacks

from .llm import get_composer_llm

logger = logging.getLogger("tripmate.graph.compose")

COMPOSER_SYSTEM = """You are arranging a day-by-day trip itinerary from real, already-fetched data.

Rules:
- You may ONLY reference place_id values from the "Available places" list below — never invent a
  place that isn't in that list. If you want a generic slot (a meal, free time, transit), leave
  place_id null and just give a title.
- Never include a price or cost anywhere in your output — pricing is computed separately from the
  real flight/stay data, not from you.
- Respect the trip's pace: relaxed = 2-3 activities/day, balanced = 3-4, packed = 5+.
- Keep each day's activity slots within a plausible single day (roughly 08:00-21:00).
- start and end must be in exactly HH:MM:SS 24-hour format (e.g. "08:00:00", not "8am" or "08:00").
"""


class PlannedSlot(BaseModel):
    day_index: int = Field(description="0-based day offset from the trip's start date")
    # Deliberately str, not datetime.time: Groq's strict tool-schema
    # validator rejects "HH:MM" (which the model naturally produces) as
    # too short for its `format: time` check, which wants "HH:MM:SS" —
    # every composer call failed validation and silently fell back to an
    # empty plan until this was loosened to a plain string, parsed by
    # _parse_time() below instead of trusting the model's exact format.
    start: str = Field(description="24-hour time, e.g. 08:00 or 08:00:00")
    end: str = Field(description="24-hour time, e.g. 11:30 or 11:30:00")
    kind: str = Field(description="one of: activity, meal, transit")
    title: str
    place_id: str | None = None


def _parse_time(value: str, fallback: time) -> time:
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value.strip(), fmt).time()
        except ValueError:
            continue
    logger.warning("Composer returned an unparseable time %r, using %s", value, fallback)
    return fallback


class ComposedPlan(BaseModel):
    slots: list[PlannedSlot]


async def compose_node(state: dict) -> dict:
    spec = state["spec"]
    places = state.get("places") or []
    weather = state.get("weather") or []
    prior_warnings = state.get("warnings") or []

    plan = await _plan_slots(spec, places, prior_warnings)

    days = _build_days(spec, plan, places, weather, state.get("flights") or [], state.get("stays") or [])
    budget, budget_warnings = _compute_budget(days, spec)

    trip = Trip(
        id=uuid.uuid4(),
        spec=spec,
        flights=state.get("flights") or [],
        stays=state.get("stays") or [],
        days=days,
        budget=budget,
        warnings=[],
        version=state.get("repair_count", 0) + 1,
    )

    return {"trip": trip, "warnings": budget_warnings}


async def _plan_slots(spec, places, prior_warnings) -> ComposedPlan:
    if not spec.destination and not spec.suggest_destination:
        return ComposedPlan(slots=[])

    places_desc = "\n".join(f"- {p.id}: {p.name} ({p.category})" for p in places[:30]) or "(none found)"
    repair_note = ""
    if prior_warnings:
        repair_note = "\nPrevious attempt had issues, fix these: " + "; ".join(prior_warnings)

    prompt = f"""
Trip: {spec.travelers} traveler(s), {spec.trip_length_days()} day(s) to {spec.destination or "a suggested destination"}.
Pace: {spec.pace}. Interests: {", ".join(spec.interests) or "none stated"}.

Available places:
{places_desc}
{repair_note}
"""

    llm = get_composer_llm()
    structured_llm = llm.with_structured_output(ComposedPlan)

    try:
        return await structured_llm.ainvoke(
            [SystemMessage(content=COMPOSER_SYSTEM), HumanMessage(content=prompt)],
            config={"callbacks": get_langfuse_callbacks(), "run_name": "compose"},
        )
    except Exception as exc:
        logger.warning("Composer LLM call failed, returning an empty plan: %s", exc)
        return ComposedPlan(slots=[])


def _build_days(spec, plan: ComposedPlan, places, weather, flights, stays) -> list[Day]:
    places_by_id = {p.id: p for p in places}
    weather_by_date = {w.date: w for w in weather}

    start = spec.date_start or date.today()
    length = spec.trip_length_days()
    days = [Day(date=start + timedelta(days=i), weather=weather_by_date.get(start + timedelta(days=i))) for i in range(length)]

    for planned in plan.slots:
        if not (0 <= planned.day_index < length):
            continue
        place = places_by_id.get(planned.place_id) if planned.place_id else None
        # A place_id the LLM invented (not in our real list) is dropped, not trusted.
        if planned.place_id and not place:
            continue

        days[planned.day_index].slots.append(
            Slot(
                start=_parse_time(planned.start, time(9, 0)),
                end=_parse_time(planned.end, time(10, 0)),
                kind=planned.kind if planned.kind in {"activity", "meal", "transit", "stay"} else "activity",
                place_id=place.id if place else None,
                title=planned.title,
                lat=place.lat if place else None,
                lng=place.lng if place else None,
                cost=None,  # activities/meals have no real pricing source (yet)
                source=place.source if place else None,
            )
        )

    if flights and days:
        first_flight = flights[0]
        days[0].slots.insert(
            0,
            Slot(
                start=time(6, 0),
                end=time(9, 0),
                kind="transit",
                title=f"Flight: {first_flight.airline} {first_flight.dep_iata}->{first_flight.arr_iata}",
                cost=first_flight.price,
                source=first_flight.source,
            ),
        )

    if stays and days:
        stay = stays[0]
        for day in days:
            day.slots.append(
                Slot(
                    start=time(20, 0),
                    end=time(23, 59),
                    kind="stay",
                    title=f"Stay: {stay.name}",
                    lat=stay.lat,
                    lng=stay.lng,
                    cost=stay.price_per_night,
                    source=stay.source,
                )
            )

    for day in days:
        day.slots.sort(key=lambda s: s.start)

    return days


def _compute_budget(days: list[Day], spec) -> tuple[BudgetBreakdown, list[str]]:
    """Sums slot costs into a single-currency total. Providers can return
    prices in whatever currency they use natively (Duffel's sandbox
    returns EUR regardless of route, for instance) — summing amount_minor
    across different currencies without conversion would silently produce
    a meaningless number, which is worse than an incomplete one. No FX
    feed is wired up yet (blueprint §05), so anything not in the primary
    currency is excluded from the total and surfaced as a warning instead
    of guessed at.
    """

    currency = spec.budget.currency if spec.budget else "INR"
    total_minor = 0
    by_category: dict[str, int] = {}
    warnings: list[str] = []

    for day in days:
        for slot in day.slots:
            if slot.cost is None:
                continue
            if slot.cost.currency != currency:
                warnings.append(
                    f"'{slot.title}' is priced in {slot.cost.currency}, not {currency} — "
                    "excluded from the budget total (no currency conversion wired up yet)"
                )
                continue
            total_minor += slot.cost.amount_minor
            by_category[slot.kind] = by_category.get(slot.kind, 0) + slot.cost.amount_minor

    total = Money(amount_minor=total_minor, currency=currency)
    fits = None
    if spec.budget is not None:
        fits = total.amount_minor <= spec.budget.amount_minor

    budget = BudgetBreakdown(
        total=total,
        limit=spec.budget,
        by_category={k: Money(amount_minor=v, currency=currency) for k, v in by_category.items()},
        fits_budget=fits,
    )
    return budget, list(dict.fromkeys(warnings))
