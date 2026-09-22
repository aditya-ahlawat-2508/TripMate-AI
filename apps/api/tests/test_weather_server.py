from datetime import date, timedelta

import custom_weather_mcp_server as weather


def test_describe_weather_code_known():
    assert weather.describe_weather_code(0) == "clear sky"
    assert weather.describe_weather_code(61) == "slight rain"


def test_describe_weather_code_unknown():
    assert weather.describe_weather_code(12345) == "unknown conditions"


def test_parse_date_roundtrip():
    assert weather.parse_date("2026-10-12") == date(2026, 10, 12)
    assert weather.parse_date(None) is None


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_get_forecast_uses_live_source_within_horizon(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        if "geocoding" in url:
            return FakeResponse({"results": [{"latitude": 1.0, "longitude": 2.0, "name": "Goa", "country": "IN"}]})
        return FakeResponse({
            "daily": {
                "time": ["2026-10-12"],
                "temperature_2m_min": [24.0],
                "temperature_2m_max": [31.0],
                "precipitation_sum": [0.0],
                "weather_code": [1],
            }
        })

    monkeypatch.setattr(weather.requests, "get", fake_get)

    start = date.today() + timedelta(days=2)
    result = weather.get_forecast("Goa", start.isoformat(), start.isoformat())

    assert result["forecast"][0]["source"] == "forecast"
    assert not any("archive" in c for c in calls)


def test_get_forecast_falls_back_to_historical_beyond_horizon(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        if "geocoding" in url:
            return FakeResponse({"results": [{"latitude": 1.0, "longitude": 2.0, "name": "Goa", "country": "IN"}]})
        return FakeResponse({
            "daily": {
                "time": ["2025-12-01"],
                "temperature_2m_min": [22.0],
                "temperature_2m_max": [29.0],
                "precipitation_sum": [1.0],
                "weather_code": [2],
            }
        })

    monkeypatch.setattr(weather.requests, "get", fake_get)

    far_out = date.today() + timedelta(days=45)
    result = weather.get_forecast("Goa", far_out.isoformat(), far_out.isoformat())

    assert result["forecast"][0]["source"] == "historical_average"
    # The historical year gets shifted back to the requested year.
    assert result["forecast"][0]["date"].startswith(str(far_out.year))


def test_get_current_weather_unknown_city(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return FakeResponse({"results": []})

    monkeypatch.setattr(weather.requests, "get", fake_get)

    result = weather.get_current_weather("Nowhereland")
    assert "error" in result
