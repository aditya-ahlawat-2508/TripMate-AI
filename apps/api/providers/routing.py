from datetime import UTC, datetime

import httpx

from custom_weather_mcp_server import geocode_city
from models import GroundOption, Source, TripSpec

OSRM_DEMO_URL = "https://router.project-osrm.org/route/v1/driving"


async def travel_time_minutes(origin: tuple[float, float], dest: tuple[float, float]) -> float | None:
    """origin/dest are (lat, lng). Used by the verifier to check whether
    consecutive slots are geographically feasible — not just at the
    top-level ground_node fan-out."""

    url = f"{OSRM_DEMO_URL}/{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params={"overview": "false"})
        response.raise_for_status()
        data = response.json()

    routes = data.get("routes") or []
    if not routes:
        return None
    return routes[0]["duration"] / 60


class OSRMGroundProvider:
    """Real, keyless driving-time/distance estimate between origin and
    destination cities via OSRM's public demo server. NOT for production
    volume — see http://project-osrm.org/. Rail/bus data for India needs an
    IRCTC-authorised partner or bus-aggregator affiliate deal (blueprint
    §05); no free keyless equivalent exists, so this provider only ever
    returns a driving estimate, clearly labeled, rather than guessing train
    times or fares.
    """

    name = "osrm-demo"
    cache_ttl_seconds = 86400  # driving time between two cities doesn't change
    result_model = GroundOption

    async def estimate(self, spec: TripSpec) -> list[GroundOption]:
        if not spec.origin or not spec.destination:
            return []

        origin_loc = geocode_city(spec.origin)
        dest_loc = geocode_city(spec.destination)
        if not origin_loc or not dest_loc:
            return []

        minutes = await travel_time_minutes(
            (origin_loc["latitude"], origin_loc["longitude"]),
            (dest_loc["latitude"], dest_loc["longitude"]),
        )
        if minutes is None:
            return []

        fetched_at = datetime.now(UTC)
        hours = minutes / 60
        return [
            GroundOption(
                mode="cab",
                description=f"~{hours:.1f} hrs driving between {spec.origin} and {spec.destination}",
                price=None,
                source=Source(provider="osrm-demo", fetched_at=fetched_at),
            ),
            GroundOption(
                mode="unavailable",
                description="Rail/bus fares aren't wired up — needs an IRCTC-authorised or bus-aggregator affiliate partner",
                price=None,
                source=Source(provider="tripmate-note", fetched_at=fetched_at),
            ),
        ]
