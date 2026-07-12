# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run the app (uvicorn with reload, serves on http://127.0.0.1:8000)
python app.py

# List every tool the MCP servers expose — the fastest way to verify MCP wiring
python test.py

# Smoke-test the legacy (non-MCP) AviationStack path directly
python tools/flight_tool.py

# Docker
docker build -t tripmate . && docker run -p 8000:8000 --env-file .env tripmate
```

There is no test suite, linter, or formatter configured. `test.py` and `mcp_client_test.py` are ad-hoc scripts, not pytest files — `test.py` just dumps the MCP tool list, and `mcp_client_test.py` is an earlier Tavily-only version of the MCP client that nothing in the app imports.

## Architecture

A request flows: `app.py` (FastAPI) → `run_travel_agent()` in `backend.py` → a compiled LangGraph → back as JSON.

**The graph is strictly linear**, with no branching or conditional edges:

```
START → flight_agent → hotel_agent → weather_agent → itinerary_agent → final_agent → END
```

All five nodes share one `TravelState` TypedDict. Each node returns a partial dict that LangGraph merges in; `messages` accumulates via `operator.add`, everything else is overwritten. The last three nodes are pure LLM calls (Groq `llama-3.3-70b-versatile`) that consume whatever earlier nodes wrote into state — so a failure in `flight_agent` degrades the itinerary rather than stopping the run.

**MCP is the tool layer.** `mcp_client.py` defines a single `MultiServerMCPClient` with three servers, and exposes async helpers that `backend.py` calls:

| Server | Transport | Backing |
|---|---|---|
| `tavily` | `streamable_http` | Remote `https://mcp.tavily.com/mcp/` (hotel search) |
| `aviationstack` | `stdio` | `uvx aviationstack-mcp` subprocess (flights) |
| `weather` | `stdio` | `custom_weather_mcp_server.py`, a local FastMCP server wrapping OpenWeather |

`custom_weather_mcp_server.py` is *not* imported — it's spawned as a subprocess by the MCP client, and its `@mcp.tool()` functions (`get_current_weather`, `get_forecast`) are discovered over stdio.

**`tools/` is dead code.** `tools/flight_tool.py` and `tools/tavily_tool.py` predate the MCP migration; their imports and call sites in `backend.py` are commented out. `flight_tool.py` still holds substantial IATA-resolution logic (country/city → airport code) that the MCP path does *not* replicate — the flight agent now just feeds raw `list_airports`/`list_airlines` dumps to the LLM. Don't edit `tools/` expecting it to affect app behavior.

## Gotchas

These are working as intended, but will surprise you.

**`initialize_mcp()` caches tools in module-level globals** (`search_tool`, `aviation_tools`, `weather_tool`, `forecast_tool`) and returns early if already populated. Tool lookup is by exact name (`tavily_search`, `get_current_weather`, `get_forecast`) via `next(...)`, so a renamed upstream tool surfaces as a bare `StopIteration`, not a useful error.

**`custom_weather_mcp_server.py` is never imported** — it is spawned as a subprocess over stdio by the MCP client. Editing it does nothing until the subprocess restarts, and its `print()` output goes to the MCP transport, not your terminal.

**Sync nodes calling async MCP helpers is load-bearing.** LangGraph nodes are sync and call `asyncio.run(...)` on async helpers; this only works because `app.py` calls `nest_asyncio.apply()` *before* importing `backend`. Do not reorder those imports. (See Things to Fix #5.)

## Things to Fix

Known outstanding defects, worst first. Nothing here is fixed yet.

### Blockers — the app does not currently run on this machine

**1. Hardcoded Windows paths in `mcp_client.py` (~lines 45–54).** The `weather` MCP server points at the original author's machine:

```python
"command": r"C:\Anaconda3\envs\travel\python.exe",
"args": [r"D:\Bappy\Coding\Youtube\Deployments\TripMate-AI-Using-MCP\custom_weather_mcp_server.py"],
```

The weather server cannot spawn on macOS/Linux, so `weather_agent` fails. Fix by deriving both from the running process — `sys.executable` and `Path(__file__).parent / "custom_weather_mcp_server.py"` — rather than substituting another absolute path.

**2. No `.env`, and no `.env.example` to copy from.** Five keys are required (see Environment below). `backend.py` raises at import if `GROQ_API_KEY` or `DATABASE_URL` is missing, so the app dies at startup. Add a committed `.env.example`.

### Structural

**3. `backend.py` connects to Postgres at import time (~lines 345–356).** `psycopg.connect()` and `checkpointer.setup()` are module-level side effects, and `app.py` imports `backend` at startup — so with no reachable database the whole app fails to boot, including `GET /health`, which needs no database at all. Move both into a lazy initializer or a FastAPI lifespan handler.

**4. `get_database_url()` force-appends `sslmode=require` (~line 39).** Correct for hosted Postgres (Render/Neon), but it breaks a plain local Postgres, which is the likely local-dev setup. Only append it for non-local hosts, or make it opt-out.

**5. `nest_asyncio` bridges sync graph nodes to async MCP helpers.** Fragile and easy to break by reordering imports. The real fix is to make all five nodes `async def` and drop `nest_asyncio` — but that must land as one change across every node, not piecemeal.

### Cleanup / quality

**6. `aviation_mcp_call()` re-fetches the entire tool list on every call** (`mcp_client.py` ~line 135), ignoring the `aviation_tools` cache that `initialize_mcp()` already populates. `flight_agent` calls it twice per request, so that is two redundant MCP round-trips per trip plan. Read from the cache.

**7. `flight_agent` feeds the LLM a raw, arbitrarily-truncated airport dump** (`backend.py` ~lines 147–151): `str(airports)[:3000]`. The model is asked to infer departure/arrival airports from whatever survived the cut. Meanwhile `tools/flight_tool.py` holds real IATA-resolution logic (`resolve_location_to_iata`, `parse_route`, plus city/country→airport maps) that the MCP migration silently dropped. Resolve the route *before* prompting, and reuse that code rather than rewriting it.

**8. Dead code.** `tools/flight_tool.py` and `tools/tavily_tool.py` are unreferenced (call sites commented out in `backend.py`); `mcp_client_test.py` is a superseded Tavily-only client nothing imports. Decide: delete, or keep `flight_tool.py` specifically to serve #7 and delete the rest.

**9. No test suite.** `test.py` and `mcp_client_test.py` are ad-hoc scripts despite the names — nothing runs under pytest.

**10. The Excalidraw diagrams have no backup.** `excalidraw_files/` (~33 MB) is gitignored and exists on local disk only. Not a code defect, but the work is unprotected — export to SVG/PNG and commit those, or move it to cloud storage.

## Environment

`.env` in the project root (gitignored, and not present by default):

```env
DATABASE_URL=postgresql://user:password@host:5432/travel_db
GROQ_API_KEY=
AVIATIONSTACK_API_KEY=
TAVILY_API_KEY=
OPENWEATHER_API_KEY=
DEFAULT_ORIGIN_IATA=DAC
```

Note the AviationStack key is read as `AVIATIONSTACK_API_KEY` from `.env`, but passed into the MCP subprocess as `AVIATION_STACK_API_KEY` (with the underscore) — both spellings are load-bearing.

`excalidraw_files/` holds design diagrams and is gitignored — the images are base64-embedded, so the folder runs to ~33 MB.
