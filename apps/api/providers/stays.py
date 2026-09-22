import json
import os
from datetime import UTC, datetime

from mcp_client import tavily_mcp_search
from models import Source, StayOffer, TripSpec

LITEAPI_KEY = os.getenv("LITEAPI_KEY")


class LiteAPIStayProvider:
    """Real room rates via LiteAPI once LITEAPI_KEY is set — needs a
    partner signup (https://liteapi.travel) this code can't create.
    Not implemented yet; returns no offers rather than guessing, same
    honesty rule as DuffelFlightProvider.
    """

    name = "liteapi"

    async def search(self, spec: TripSpec) -> list[StayOffer]:
        if not LITEAPI_KEY:
            return []
        return []  # not implemented — see docs/progress.md


class TavilyStaySearchProvider:
    """Fallback while no structured rate provider is configured: hotel
    *names and links* from web search, never a price. Tavily has no real
    room-rate data, so price_per_night stays None here — an unsourced
    number is worse than no number.
    """

    name = "tavily-search"

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
