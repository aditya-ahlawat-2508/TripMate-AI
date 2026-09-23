import pytest

import providers.base as base_module
from models import DayWeather, TripSpec


class FakeCachedProvider:
    """A provider that counts how many times it was actually called, to
    prove a cache hit skips the real call entirely."""

    name = "fake-cached"
    cache_ttl_seconds = 300
    result_model = DayWeather

    def __init__(self, results):
        self._results = results
        self.call_count = 0

    async def forecast(self, spec):
        self.call_count += 1
        return self._results


class FakeUncachedProvider:
    name = "fake-uncached"
    # no cache_ttl_seconds / result_model — must never be cached

    def __init__(self, results):
        self._results = results
        self.call_count = 0

    async def forecast(self, spec):
        self.call_count += 1
        return self._results


@pytest.fixture
def in_memory_cache(monkeypatch):
    store: dict[str, object] = {}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl):
        store[key] = value

    monkeypatch.setattr(base_module, "cache_get", fake_get)
    monkeypatch.setattr(base_module, "cache_set", fake_set)
    return store


@pytest.mark.asyncio
async def test_cache_hit_skips_the_real_call(in_memory_cache):
    weather = [DayWeather(date="2026-11-15", condition="clear sky")]
    provider = FakeCachedProvider(weather)
    spec = TripSpec(origin="Delhi", destination="Goa")

    r1 = await base_module.call_provider(provider, "forecast", spec, [])
    r2 = await base_module.call_provider(provider, "forecast", spec, [])

    assert provider.call_count == 1  # second call was served from cache
    assert r1 == r2
    assert r2[0].condition == "clear sky"


@pytest.mark.asyncio
async def test_cache_key_differs_by_spec(in_memory_cache):
    provider = FakeCachedProvider([DayWeather(date="2026-11-15", condition="clear sky")])

    await base_module.call_provider(provider, "forecast", TripSpec(destination="Goa"), [])
    await base_module.call_provider(provider, "forecast", TripSpec(destination="Manali"), [])

    assert provider.call_count == 2  # different destinations -> different cache keys


@pytest.mark.asyncio
async def test_provider_without_cache_config_is_never_cached(in_memory_cache):
    provider = FakeUncachedProvider([DayWeather(date="2026-11-15", condition="clear sky")])
    spec = TripSpec(destination="Goa")

    await base_module.call_provider(provider, "forecast", spec, [])
    await base_module.call_provider(provider, "forecast", spec, [])

    assert provider.call_count == 2  # no caching -> called every time
    assert in_memory_cache == {}


@pytest.mark.asyncio
async def test_empty_result_is_not_cached(in_memory_cache):
    provider = FakeCachedProvider([])
    spec = TripSpec(destination="Goa")

    await base_module.call_provider(provider, "forecast", spec, [])
    await base_module.call_provider(provider, "forecast", spec, [])

    assert provider.call_count == 2  # nothing worth caching, so no false "no data" cache
    assert in_memory_cache == {}


@pytest.mark.asyncio
async def test_cached_result_round_trips_through_json(in_memory_cache):
    weather = [DayWeather(date="2026-11-15", temp_min_c=24.5, temp_max_c=31.2, condition="clear sky", precipitation_mm=0.0)]
    provider = FakeCachedProvider(weather)
    spec = TripSpec(destination="Goa")

    await base_module.call_provider(provider, "forecast", spec, [])
    result = await base_module.call_provider(provider, "forecast", spec, [])

    assert provider.call_count == 1
    assert isinstance(result[0], DayWeather)
    assert result[0].temp_min_c == 24.5
    assert str(result[0].date) == "2026-11-15"
