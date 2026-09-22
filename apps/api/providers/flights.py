import os
from datetime import UTC, datetime

import httpx

from models import FlightOffer, Money, Source, TripSpec
from tools.flight_tool import resolve_location_to_iata

DUFFEL_API_KEY = os.getenv("DUFFEL_API_KEY")
DUFFEL_OFFER_REQUESTS_URL = "https://api.duffel.com/air/offer_requests"


class DuffelFlightProvider:
    """Real fares via Duffel's Offer Requests API, implemented against
    Duffel's public v2 REST docs. Needs DUFFEL_API_KEY — a self-serve
    Duffel account (https://duffel.com) that this code cannot create on
    its own.

    IMPORTANT: this has not been exercised against a live key or a real
    response as of this commit — there was none available. call_provider()
    in providers/base.py wraps every call, so if the request shape or
    response parsing is wrong, it surfaces as a warning ("couldn't fetch
    live flight data") rather than crashing the graph or inventing a price.
    Once a real key exists, this is the first thing to verify end-to-end
    and fix from real error messages.
    """

    name = "duffel"

    async def search(self, spec: TripSpec) -> list[FlightOffer]:
        if not DUFFEL_API_KEY:
            return []
        if not spec.origin or not spec.destination or not spec.date_start:
            return []

        dep_iata = resolve_location_to_iata(spec.origin)
        arr_iata = resolve_location_to_iata(spec.destination)
        if not dep_iata or not arr_iata:
            return []

        payload = {
            "data": {
                "slices": [
                    {
                        "origin": dep_iata,
                        "destination": arr_iata,
                        "departure_date": spec.date_start.isoformat(),
                    }
                ],
                "passengers": [{"type": "adult"} for _ in range(max(spec.travelers, 1))],
                "cabin_class": "economy",
            }
        }

        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(
                DUFFEL_OFFER_REQUESTS_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {DUFFEL_API_KEY}",
                    "Duffel-Version": "v2",
                    "Content-Type": "application/json",
                },
                params={"return_offers": "true"},
            )
            response.raise_for_status()
            data = response.json()

        fetched_at = datetime.now(UTC)
        offers = []
        for offer in (data.get("data", {}).get("offers") or [])[:10]:
            slices = offer.get("slices") or [{}]
            segments = slices[0].get("segments") or [{}]
            segment = segments[0]

            offers.append(
                FlightOffer(
                    id=offer["id"],
                    airline=(segment.get("operating_carrier") or {}).get("name", "Unknown airline"),
                    dep_iata=dep_iata,
                    arr_iata=arr_iata,
                    depart_at=segment.get("departing_at"),
                    arrive_at=segment.get("arriving_at"),
                    duration_minutes=None,
                    price=Money(
                        amount_minor=round(float(offer["total_amount"]) * 100),
                        currency=offer["total_currency"],
                    ),
                    source=Source(provider="duffel", fetched_at=fetched_at),
                )
            )
        return offers
