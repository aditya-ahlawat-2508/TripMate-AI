"""Provider adapter interfaces (structural typing via Protocol) so vendors
can be swapped without touching the graph, and mocked in tests.

Every provider must degrade to an empty list on failure or missing
configuration — never raise up through the graph and never invent data.
call_provider() enforces that at the call site.
"""

import hashlib
import json
import logging
from typing import Protocol, TypeVar

from models import DayWeather, FlightOffer, GroundOption, Place, StayOffer, TripSpec

from .cache import cache_get, cache_set

logger = logging.getLogger("tripmate.providers")

T = TypeVar("T")


class FlightProvider(Protocol):
    name: str

    async def search(self, spec: TripSpec) -> list[FlightOffer]: ...


class StayProvider(Protocol):
    name: str

    async def search(self, spec: TripSpec) -> list[StayOffer]: ...


class WeatherProvider(Protocol):
    name: str

    async def forecast(self, spec: TripSpec) -> list[DayWeather]: ...


class PlacesProvider(Protocol):
    name: str

    async def search(self, spec: TripSpec) -> list[Place]: ...


class GroundProvider(Protocol):
    name: str

    async def estimate(self, spec: TripSpec) -> list[GroundOption]: ...


def _cache_key(provider_name: str, method_name: str, spec: TripSpec) -> str:
    """Normalized per blueprint §05 ("keyed by normalized query"): only
    the fields that actually change a provider's answer, not the whole
    spec (interests/constraints/pace don't affect a flight search)."""

    relevant = {
        "origin": spec.origin,
        "destination": spec.destination,
        "date_start": spec.date_start.isoformat() if spec.date_start else None,
        "date_end": spec.date_end.isoformat() if spec.date_end else None,
        "travelers": spec.travelers,
    }
    digest = hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()[:16]
    return f"provider:{provider_name}:{method_name}:{digest}"


async def call_provider(provider, method_name: str, spec: TripSpec, warnings: list[str]) -> list:
    """Runs provider.<method_name>(spec), turning any exception into a
    warning instead of letting it crash the graph — a failed provider
    produces a visible warning, never invented data.

    Caches by (provider, method, normalized spec) when the provider
    declares cache_ttl_seconds and result_model (the Pydantic model to
    reconstruct cached JSON back into) — providers that don't declare
    both (e.g. ones without a stable/meaningful TTL) are never cached.
    A cache miss or a Redis outage both fall through to a live call,
    same as an uncached provider; a live call's result is still cached
    for next time even after a miss.
    """

    ttl = getattr(provider, "cache_ttl_seconds", None)
    result_model = getattr(provider, "result_model", None)
    provider_name = getattr(provider, "name", str(provider))
    key = _cache_key(provider_name, method_name, spec) if ttl and result_model else None

    if key:
        cached = await cache_get(key)
        if cached is not None:
            return [result_model.model_validate(item) for item in cached]

    method = getattr(provider, method_name)
    try:
        result = await method(spec)
        result = result or []
    except Exception as exc:
        logger.warning("Provider %s failed: %s", provider_name, exc)
        warnings.append(f"Couldn't fetch live data from {provider_name}: {exc}")
        return []

    if key and result:
        await cache_set(key, [item.model_dump(mode="json") for item in result], ttl)

    return result
