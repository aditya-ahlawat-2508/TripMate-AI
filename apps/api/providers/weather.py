import json

from mcp_client import forecast_mcp_search
from models import DayWeather, TripSpec


def _unwrap_mcp_result(raw) -> dict | None:
    """langchain-mcp-adapters returns tool output as a list of MCP content
    blocks (e.g. [{"type": "text", "text": "<json>"}]), not the tool's
    return value directly. The old free-text weather_agent never noticed
    because it just stringified whatever came back into a prompt."""

    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list) and raw:
        first = raw[0]
        text = first.get("text") if isinstance(first, dict) else None
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return None
    return None


class OpenMeteoWeatherProvider:
    """Real, keyless — reuses the same Open-Meteo MCP helper the legacy
    weather_agent uses (see custom_weather_mcp_server.py)."""

    name = "open-meteo"
    cache_ttl_seconds = 3600  # forecasts update a few times a day, not per-request
    result_model = DayWeather

    async def forecast(self, spec: TripSpec) -> list[DayWeather]:
        if not spec.destination:
            return []

        start = spec.date_start.isoformat() if spec.date_start else None
        end = spec.date_end.isoformat() if spec.date_end else None

        raw = await forecast_mcp_search(spec.destination, start, end)
        result = _unwrap_mcp_result(raw)
        if not result or "error" in result:
            return []

        days = []
        for entry in result.get("forecast", []):
            days.append(
                DayWeather(
                    date=entry["date"],
                    temp_min_c=entry.get("temp_min_c"),
                    temp_max_c=entry.get("temp_max_c"),
                    condition=entry.get("condition", "unknown"),
                    precipitation_mm=entry.get("precipitation_mm"),
                    is_historical_average=entry.get("source") == "historical_average",
                )
            )
        return days
