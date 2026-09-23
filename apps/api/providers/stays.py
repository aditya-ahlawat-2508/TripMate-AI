import json
import os
from datetime import UTC, datetime, timedelta

import httpx

from custom_weather_mcp_server import geocode_city
from mcp_client import tavily_mcp_search
from models import Money, Source, StayOffer, TripSpec

LITEAPI_KEY = os.getenv("LITEAPI_KEY")
LITEAPI_HOTELS_URL = "https://api.liteapi.travel/v3.0/data/hotels"
LITEAPI_RATES_URL = "https://api.liteapi.travel/v3.0/hotels/rates"


class LiteAPIStayProvider:
    """Real room rates via LiteAPI/Nuitee Connect (sandbox), gated on
    LITEAPI_KEY. Two calls: GET /data/hotels by lat/lng (reuses the same
    geocode_city as the places/routing providers — LiteAPI's hotel search
    requires a country code, lat/lng, or a few other options that don't
    fit a free-text city name well, and coordinates already work
    everywhere else in this codebase), then POST /hotels/rates for the
    actual prices. retailRate.total is the rate for the whole stay, not
    per night — divided by night count below.
    """

    name = "liteapi"
    cache_ttl_seconds = 300
    result_model = StayOffer

    async def search(self, spec: TripSpec, radius_m: int = 15000, limit: int = 8) -> list[StayOffer]:
        if not LITEAPI_KEY or not spec.destination:
            return []

        location = geocode_city(spec.destination)
        if not location:
            return []

        checkin = spec.date_start or (datetime.now(UTC).date() + timedelta(days=30))
        checkout = spec.date_end or (checkin + timedelta(days=1))
        if checkout <= checkin:
            checkout = checkin + timedelta(days=1)
        nights = (checkout - checkin).days
        currency = spec.budget.currency if spec.budget else "INR"

        headers = {"X-API-Key": LITEAPI_KEY, "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=25) as client:
            hotels_res = await client.get(
                LITEAPI_HOTELS_URL,
                headers=headers,
                params={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "radius": radius_m,
                    "limit": limit,
                },
            )
            hotels_res.raise_for_status()
            hotels = {h["id"]: h for h in hotels_res.json().get("data", [])}
            if not hotels:
                return []

            rates_res = await client.post(
                LITEAPI_RATES_URL,
                headers=headers,
                json={
                    "hotelIds": list(hotels.keys()),
                    "checkin": checkin.isoformat(),
                    "checkout": checkout.isoformat(),
                    "currency": currency,
                    "guestNationality": "IN",
                    "occupancies": [{"adults": max(spec.travelers, 1)}],
                },
            )
            rates_res.raise_for_status()
            rate_entries = rates_res.json().get("data", [])

        fetched_at = datetime.now(UTC)
        offers = []
        for entry in rate_entries:
            hotel = hotels.get(entry.get("hotelId"))
            room_types = entry.get("roomTypes") or []
            if not hotel or not room_types:
                continue
            rates = room_types[0].get("rates") or []
            if not rates:
                continue
            total = ((rates[0].get("retailRate") or {}).get("total") or [{}])[0]
            amount = total.get("amount")

            offers.append(
                StayOffer(
                    id=hotel["id"],
                    name=hotel.get("name", "Unknown hotel"),
                    rating=hotel.get("rating"),
                    lat=hotel.get("latitude"),
                    lng=hotel.get("longitude"),
                    price_per_night=Money(amount_minor=round(amount / nights * 100), currency=total.get("currency", currency))
                    if amount is not None
                    else None,
                    source=Source(provider="liteapi", fetched_at=fetched_at),
                )
            )
        return offers


class TavilyStaySearchProvider:
    """Fallback while no structured rate provider is configured: hotel
    *names and links* from web search, never a price. Tavily has no real
    room-rate data, so price_per_night stays None here — an unsourced
    number is worse than no number.
    """

    name = "tavily-search"
    cache_ttl_seconds = 3600  # generic search results, not real-time pricing
    result_model = StayOffer

    async def search(self, spec: TripSpec) -> list[StayOffer]:
        if not spec.destination:
            return []

        raw = await tavily_mcp_search(f"hotels in {spec.destination}")
        items = _extract_items(raw)

        fetched_at = datetime.now(UTC)
        offers = []
        for i, item in enumerate(items[:8]):
            title, url = _extract_title_url(item)
            if not title:
                continue
            offers.append(
                StayOffer(
                    id=f"tavily-{i}",
                    name=title,
                    price_per_night=None,
                    source=Source(provider="tavily-search", fetched_at=fetched_at, url=url),
                )
            )
        return offers


def _extract_items(raw) -> list:
    # langchain-mcp-adapters wraps tool output as a list of MCP content
    # blocks (e.g. [{"type": "text", "text": "<json>"}]) — unwrap that
    # before treating a bare list as the items themselves.
    if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict) and "text" in raw[0]:
        try:
            raw = json.loads(raw[0]["text"])
        except json.JSONDecodeError:
            return []

    if isinstance(raw, dict):
        return raw.get("results", [])
    if isinstance(raw, list):
        return raw
    return []


def _extract_title_url(item) -> tuple[str | None, str | None]:
    if isinstance(item, dict):
        return item.get("title"), item.get("url")
    return None, None
