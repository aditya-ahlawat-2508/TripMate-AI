"""Provider adapter interfaces (structural typing via Protocol) so vendors
can be swapped without touching the graph, and mocked in tests.

Every provider must degrade to an empty list on failure or missing
configuration — never raise up through the graph and never invent data.
call_provider() enforces that at the call site.
"""

import logging
from typing import Protocol, TypeVar

from models import DayWeather, FlightOffer, GroundOption, Place, StayOffer, TripSpec

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


async def call_provider(provider, method_name: str, spec: TripSpec, warnings: list[str]) -> list:
    """Runs provider.<method_name>(spec), turning any exception into a
    warning instead of letting it crash the graph — a failed provider
    produces a visible warning, never invented data.
    """

    method = getattr(provider, method_name)
    try:
        result = await method(spec)
        return result or []
    except Exception as exc:
        logger.warning("Provider %s failed: %s", getattr(provider, "name", provider), exc)
        warnings.append(f"Couldn't fetch live data from {getattr(provider, 'name', 'a provider')}: {exc}")
        return []
