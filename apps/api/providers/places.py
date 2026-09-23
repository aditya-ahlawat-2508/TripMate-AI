from datetime import UTC, datetime

import httpx

from custom_weather_mcp_server import geocode_city
from models import Place, Source, TripSpec

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


class OverpassPlacesProvider:
    """Real, keyless POI data from OpenStreetMap via the public Overpass
    API. Like the OSRM demo server below, this is a shared public instance —
    fine for a portfolio/demo, not for production volume (see
    https://overpass-api.de/api/status for its own rate-limit guidance).
    Swap for a self-hosted Overpass instance or Google Places before
    launch-scale traffic.
    """

    name = "overpass"
    # Long TTL — POIs barely change day to day, and this also means a
    # transient Overpass 504 (seen live, docs/progress.md) only costs one
    # real request per destination instead of one per trip request.
    cache_ttl_seconds = 86400
    result_model = Place

    async def search(self, spec: TripSpec, radius_m: int = 5000, limit: int = 20) -> list[Place]:
        if not spec.destination:
            return []

        location = geocode_city(spec.destination)
        if not location:
            return []

        lat, lng = location["latitude"], location["longitude"]
        query = f"""
        [out:json][timeout:20];
        (
          node["tourism"="attraction"](around:{radius_m},{lat},{lng});
          node["amenity"="restaurant"](around:{radius_m},{lat},{lng});
          node["amenity"="cafe"](around:{radius_m},{lat},{lng});
        );
        out center {limit * 2};
        """

        async with httpx.AsyncClient(timeout=25) as client:
            # Overpass's public instance 406s requests without a
            # descriptive User-Agent (its usage policy asks for one).
            response = await client.post(
                OVERPASS_URL,
                data={"data": query},
                headers={"User-Agent": "TripMateAI/0.1 (https://github.com/aditya-ahlawat-2508/TripMate-AI)"},
            )
            response.raise_for_status()
            data = response.json()

        fetched_at = datetime.now(UTC)
        places: list[Place] = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name")
            place_lat = element.get("lat") or (element.get("center") or {}).get("lat")
            place_lng = element.get("lon") or (element.get("center") or {}).get("lon")
            if not name or place_lat is None or place_lng is None:
                continue

            places.append(
                Place(
                    id=f"osm-{element['type']}-{element['id']}",
                    name=name,
                    category=tags.get("tourism") or tags.get("amenity") or "poi",
                    lat=place_lat,
                    lng=place_lng,
                    source=Source(
                        provider="overpass",
                        fetched_at=fetched_at,
                        url="https://www.openstreetmap.org/",
                    ),
                )
            )
            if len(places) >= limit:
                break

        return places
