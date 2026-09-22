from datetime import date, datetime, timedelta

import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather MCP Server")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Open-Meteo's free daily forecast only covers this many days ahead. Dates
# further out fall back to a historical-average lookup instead of guessing.
FORECAST_HORIZON_DAYS = 16

# WMO weather codes -> short human description.
# https://open-meteo.com/en/docs#weathervariables
WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "dense freezing drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "heavy freezing rain",
    71: "slight snow fall", 73: "moderate snow fall", 75: "heavy snow fall",
    77: "snow grains",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    85: "slight snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
}


def describe_weather_code(code) -> str:
    return WEATHER_CODES.get(code, "unknown conditions")


def geocode_city(city: str):
    response = requests.get(
        GEOCODING_URL,
        params={"name": city, "count": 1},
        timeout=15,
    )
    response.raise_for_status()
    results = response.json().get("results") or []

    if not results:
        return None

    match = results[0]
    return {
        "latitude": match["latitude"],
        "longitude": match["longitude"],
        "resolved_name": match.get("name", city),
        "country": match.get("country", ""),
    }


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


@mcp.tool()
def get_current_weather(city: str) -> dict:
    """Current conditions for a city, via Open-Meteo (no API key required)."""

    location = geocode_city(city)
    if not location:
        return {"error": f"Could not find a location matching '{city}'"}

    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "timezone": "auto",
        },
        timeout=15,
    )
    response.raise_for_status()
    current = response.json().get("current", {})

    return {
        "city": location["resolved_name"],
        "country": location["country"],
        "temperature_c": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "condition": describe_weather_code(current.get("weather_code")),
        "wind_speed_kmh": current.get("wind_speed_10m"),
    }


@mcp.tool()
def get_forecast(city: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    """
    Daily forecast for a city over a date range.

    start_date / end_date are ISO dates ("YYYY-MM-DD"). If omitted, defaults
    to today through the next 5 days. Open-Meteo's forecast only covers about
    16 days ahead; requests further out automatically fall back to a
    historical average (last year's actual weather on those calendar dates),
    clearly labeled as such rather than treated as a forecast.
    """

    location = geocode_city(city)
    if not location:
        return {"error": f"Could not find a location matching '{city}'"}

    today = date.today()
    start = parse_date(start_date) or today
    end = parse_date(end_date) or (start + timedelta(days=4))

    if end < start:
        start, end = end, start

    horizon = today + timedelta(days=FORECAST_HORIZON_DAYS)

    if end <= horizon:
        return _live_forecast(location, start, end)

    if start > horizon:
        return _historical_average_forecast(location, start, end)

    # Range straddles the forecast horizon: stitch both sources together.
    live = _live_forecast(location, start, horizon)
    historical = _historical_average_forecast(location, horizon + timedelta(days=1), end)
    return {
        "city": location["resolved_name"],
        "country": location["country"],
        "forecast": live["forecast"] + historical["forecast"],
    }


def _live_forecast(location: dict, start: date, end: date) -> dict:
    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "timezone": "auto",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        timeout=15,
    )
    response.raise_for_status()
    daily = response.json().get("daily", {})

    forecast = [
        {
            "date": day,
            "temp_min_c": daily["temperature_2m_min"][i],
            "temp_max_c": daily["temperature_2m_max"][i],
            "precipitation_mm": daily["precipitation_sum"][i],
            "condition": describe_weather_code(daily["weather_code"][i]),
            "source": "forecast",
        }
        for i, day in enumerate(daily.get("time", []))
    ]

    return {
        "city": location["resolved_name"],
        "country": location["country"],
        "forecast": forecast,
    }


def _historical_average_forecast(location: dict, start: date, end: date) -> dict:
    """Typical conditions for calendar dates too far out to forecast, based
    on the same dates one year ago."""

    if start > end:
        return {"city": location["resolved_name"], "country": location["country"], "forecast": []}

    last_year_start = start.replace(year=start.year - 1)
    last_year_end = end.replace(year=end.year - 1)

    response = requests.get(
        ARCHIVE_URL,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "timezone": "auto",
            "start_date": last_year_start.isoformat(),
            "end_date": last_year_end.isoformat(),
        },
        timeout=15,
    )
    response.raise_for_status()
    daily = response.json().get("daily", {})

    forecast = []
    for i, day in enumerate(daily.get("time", [])):
        this_year_date = datetime.strptime(day, "%Y-%m-%d").date().replace(year=start.year)
        forecast.append(
            {
                "date": this_year_date.isoformat(),
                "temp_min_c": daily["temperature_2m_min"][i],
                "temp_max_c": daily["temperature_2m_max"][i],
                "precipitation_mm": daily["precipitation_sum"][i],
                "condition": describe_weather_code(daily["weather_code"][i]),
                "source": "historical_average",
            }
        )

    return {
        "city": location["resolved_name"],
        "country": location["country"],
        "forecast": forecast,
    }


if __name__ == "__main__":
    mcp.run()
