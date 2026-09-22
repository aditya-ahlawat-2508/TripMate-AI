import pytest

import providers.flights as flights_module
import providers.places as places_module
import providers.routing as routing_module
import providers.stays as stays_module
import providers.weather as weather_module
from models import TripSpec


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeAsyncClient:
    """Mimics httpx.AsyncClient's async-context-manager + get/post surface
    with a single canned response — no live network calls in tests."""

    def __init__(self, response):
        self._response = response

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        return self._response

    async def post(self, *args, **kwargs):
        return self._response


@pytest.mark.asyncio
async def test_overpass_provider_parses_named_elements(monkeypatch):
    fake_response = FakeResponse({
        "elements": [
            {"type": "node", "id": 1, "lat": 15.5, "lon": 73.8, "tags": {"name": "Baga Beach", "tourism": "attraction"}},
            {"type": "node", "id": 2, "lat": 15.6, "lon": 73.9, "tags": {}},  # no name -> skipped
        ]
    })
    monkeypatch.setattr(places_module.httpx, "AsyncClient", FakeAsyncClient(fake_response))
    monkeypatch.setattr(places_module, "geocode_city", lambda city: {"latitude": 15.5, "longitude": 73.8})

    provider = places_module.OverpassPlacesProvider()
    result = await provider.search(TripSpec(destination="Goa"))

    assert len(result) == 1
    assert result[0].name == "Baga Beach"
    assert result[0].source.provider == "overpass"


@pytest.mark.asyncio
async def test_overpass_provider_no_destination_returns_empty():
    provider = places_module.OverpassPlacesProvider()
    assert await provider.search(TripSpec()) == []


@pytest.mark.asyncio
async def test_overpass_provider_unresolvable_city_returns_empty(monkeypatch):
    monkeypatch.setattr(places_module, "geocode_city", lambda city: None)
    provider = places_module.OverpassPlacesProvider()
    assert await provider.search(TripSpec(destination="Nowhereland")) == []


@pytest.mark.asyncio
async def test_osrm_ground_provider_returns_driving_estimate(monkeypatch):
    fake_response = FakeResponse({"routes": [{"duration": 36000, "distance": 500000}]})
    monkeypatch.setattr(routing_module.httpx, "AsyncClient", FakeAsyncClient(fake_response))
    monkeypatch.setattr(
        routing_module,
        "geocode_city",
        lambda city: {"latitude": 28.6, "longitude": 77.2} if city == "Delhi" else {"latitude": 15.5, "longitude": 73.8},
    )

    provider = routing_module.OSRMGroundProvider()
    result = await provider.estimate(TripSpec(origin="Delhi", destination="Goa"))

    assert len(result) == 2
    assert result[0].mode == "cab"
    assert "hrs driving" in result[0].description
    assert result[1].mode == "unavailable"


@pytest.mark.asyncio
async def test_osrm_ground_provider_missing_origin_returns_empty():
    provider = routing_module.OSRMGroundProvider()
    assert await provider.estimate(TripSpec(destination="Goa")) == []


@pytest.mark.asyncio
async def test_duffel_provider_returns_empty_without_api_key(monkeypatch):
    monkeypatch.setattr(flights_module, "DUFFEL_API_KEY", None)
    provider = flights_module.DuffelFlightProvider()
    spec = TripSpec(origin="Delhi", destination="Goa")
    assert await provider.search(spec) == []


@pytest.mark.asyncio
async def test_liteapi_provider_returns_empty_without_api_key(monkeypatch):
    monkeypatch.setattr(stays_module, "LITEAPI_KEY", None)
    provider = stays_module.LiteAPIStayProvider()
    assert await provider.search(TripSpec(destination="Goa")) == []


def test_tavily_extract_items_handles_dict_and_list():
    assert stays_module._extract_items({"results": [1, 2]}) == [1, 2]
    assert stays_module._extract_items([1, 2]) == [1, 2]
    assert stays_module._extract_items("unexpected string") == []


def test_tavily_extract_title_url():
    assert stays_module._extract_title_url({"title": "Hotel X", "url": "http://x"}) == ("Hotel X", "http://x")
    assert stays_module._extract_title_url("not a dict") == (None, None)


@pytest.mark.asyncio
async def test_tavily_stay_provider_never_sets_a_price(monkeypatch):
    async def fake_search(query):
        return {"results": [{"title": "Some Hotel", "url": "http://example.com"}]}

    monkeypatch.setattr(stays_module, "tavily_mcp_search", fake_search)
    provider = stays_module.TavilyStaySearchProvider()
    result = await provider.search(TripSpec(destination="Goa"))

    assert len(result) == 1
    assert result[0].price_per_night is None


def test_extract_items_unwraps_mcp_content_block():
    # This is the actual shape langchain-mcp-adapters returns from a tool
    # call — a one-item list of {"type": "text", "text": "<json>"} — not
    # the tool's return value directly.
    import json as json_module

    raw = [{"type": "text", "text": json_module.dumps({"results": [{"title": "Hotel A"}]})}]
    assert stays_module._extract_items(raw) == [{"title": "Hotel A"}]


def test_extract_items_handles_malformed_content_block():
    assert stays_module._extract_items([{"type": "text", "text": "not json"}]) == []


def test_unwrap_mcp_result_handles_content_block_list():
    import json as json_module

    raw = [{"type": "text", "text": json_module.dumps({"forecast": [{"date": "2026-10-12"}]})}]
    result = weather_module._unwrap_mcp_result(raw)
    assert result == {"forecast": [{"date": "2026-10-12"}]}


def test_unwrap_mcp_result_passes_through_plain_dict():
    assert weather_module._unwrap_mcp_result({"forecast": []}) == {"forecast": []}


def test_unwrap_mcp_result_returns_none_for_garbage():
    assert weather_module._unwrap_mcp_result("nonsense") is None
    assert weather_module._unwrap_mcp_result([]) is None


@pytest.mark.asyncio
async def test_open_meteo_provider_parses_wrapped_mcp_response(monkeypatch):
    async def fake_forecast_mcp_search(city, start, end):
        import json as json_module

        payload = {
            "forecast": [
                {"date": "2026-10-12", "temp_min_c": 24, "temp_max_c": 31, "condition": "clear sky", "precipitation_mm": 0, "source": "forecast"}
            ]
        }
        return [{"type": "text", "text": json_module.dumps(payload)}]

    monkeypatch.setattr(weather_module, "forecast_mcp_search", fake_forecast_mcp_search)
    provider = weather_module.OpenMeteoWeatherProvider()
    result = await provider.forecast(TripSpec(destination="Goa"))

    assert len(result) == 1
    assert result[0].condition == "clear sky"
