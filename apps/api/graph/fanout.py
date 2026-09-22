from providers.base import call_provider
from providers.flights import DuffelFlightProvider
from providers.places import OverpassPlacesProvider
from providers.routing import OSRMGroundProvider
from providers.stays import LiteAPIStayProvider, TavilyStaySearchProvider
from providers.weather import OpenMeteoWeatherProvider


def make_flights_node(provider=None):
    provider = provider or DuffelFlightProvider()

    async def flights_node(state: dict) -> dict:
        warnings: list[str] = []
        offers = await call_provider(provider, "search", state["spec"], warnings)
        if not offers:
            warnings.append("No live flight fares available — see providers/flights.py")
        return {"flights": offers, "warnings": warnings}

    return flights_node


def make_stays_node(providers=None):
    providers = providers or [LiteAPIStayProvider(), TavilyStaySearchProvider()]

    async def stays_node(state: dict) -> dict:
        warnings: list[str] = []
        offers: list = []
        for provider in providers:
            result = await call_provider(provider, "search", state["spec"], warnings)
            offers.extend(result)
            if result:
                break
        if not offers:
            warnings.append("Couldn't fetch live hotel prices")
        return {"stays": offers, "warnings": warnings}

    return stays_node


def make_weather_node(provider=None):
    provider = provider or OpenMeteoWeatherProvider()

    async def weather_node(state: dict) -> dict:
        warnings: list[str] = []
        forecast = await call_provider(provider, "forecast", state["spec"], warnings)
        return {"weather": forecast, "warnings": warnings}

    return weather_node


def make_places_node(provider=None):
    provider = provider or OverpassPlacesProvider()

    async def places_node(state: dict) -> dict:
        warnings: list[str] = []
        places = await call_provider(provider, "search", state["spec"], warnings)
        return {"places": places, "warnings": warnings}

    return places_node


def make_ground_node(provider=None):
    provider = provider or OSRMGroundProvider()

    async def ground_node(state: dict) -> dict:
        warnings: list[str] = []
        options = await call_provider(provider, "estimate", state["spec"], warnings)
        return {"ground": options, "warnings": warnings}

    return ground_node
