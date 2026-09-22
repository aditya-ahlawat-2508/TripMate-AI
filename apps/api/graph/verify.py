import math

MAX_REPAIRS = 2
MAX_DAILY_ACTIVITY_HOURS = 10
MAX_PLACE_DISTANCE_KM = 60  # generous city-radius sanity check, not a hard geofence


def verify_node(state: dict) -> dict:
    """Deterministic checks only — no LLM call. A geography check via
    distance from the places-query center is more reliable and more
    testable than the blueprint's suggested "cheap LLM check", and reaches
    the same goal (catch wrong-city placements) without another LLM
    round-trip.
    """

    trip = state["trip"]
    issues: list[str] = []

    issues.extend(_check_sourced_prices(trip))
    issues.extend(_check_daily_hours(trip))
    issues.extend(_check_geography(trip, state.get("places") or []))

    repair_count = state.get("repair_count", 0)
    if issues and repair_count < MAX_REPAIRS:
        return {"needs_repair": True, "warnings": issues, "repair_count": repair_count + 1}

    # Finalizing: fold in every warning accumulated across the whole run
    # (provider fan-out failures included, not just this verify pass) —
    # otherwise a failed flights/stays/weather provider never surfaces to
    # the caller at all, since compose_node always starts trip.warnings=[].
    all_warnings = (state.get("warnings") or []) + issues
    trip.warnings = list(dict.fromkeys(all_warnings))
    return {"needs_repair": False, "trip": trip, "warnings": issues}


def route_after_verify(state: dict) -> str:
    return "repair" if state.get("needs_repair") else "done"


def _check_sourced_prices(trip) -> list[str]:
    issues = []
    for day in trip.days:
        for slot in day.slots:
            if slot.cost is not None and slot.source is None:
                issues.append(f"Priced slot '{slot.title}' on {day.date} has no source — dropping its price")
                slot.cost = None
    return issues


def _check_daily_hours(trip) -> list[str]:
    issues = []
    for day in trip.days:
        total_minutes = sum(_minutes_between(s.start, s.end) for s in day.slots if s.kind in {"activity", "meal"})
        if total_minutes > MAX_DAILY_ACTIVITY_HOURS * 60:
            issues.append(
                f"{day.date} has {total_minutes / 60:.1f}h of activities, above the {MAX_DAILY_ACTIVITY_HOURS}h comfort limit"
            )
    return issues


def _check_geography(trip, places) -> list[str]:
    if not places:
        return []
    center_lat = sum(p.lat for p in places) / len(places)
    center_lng = sum(p.lng for p in places) / len(places)

    issues = []
    for day in trip.days:
        for slot in day.slots:
            if slot.lat is None or slot.lng is None:
                continue
            distance = _haversine_km(center_lat, center_lng, slot.lat, slot.lng)
            if distance > MAX_PLACE_DISTANCE_KM:
                issues.append(f"'{slot.title}' is {distance:.0f}km from the destination area — likely wrong city")
    return issues


def _minutes_between(start, end) -> int:
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    return max(end_min - start_min, 0)


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
