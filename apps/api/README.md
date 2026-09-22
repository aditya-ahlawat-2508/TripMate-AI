# ✈️ TripMate AI — A Multi-Agent Travel Planner with MCP

An open-source AI travel planner that turns a natural-language trip request into a practical travel plan with flight suggestions, hotel ideas, weather details, and a day-by-day itinerary. The project uses a multi-agent workflow built with LangGraph, LangChain, FastAPI, and MCP tooling.

## Why this project?

Planning a trip usually means jumping between multiple websites, tools, and spreadsheets. This project brings that flow into one experience by combining:

- a flight-search agent,
- a hotel-research agent,
- a weather agent,
- an itinerary-planning agent, and
- a final response agent,

all coordinated through a LangGraph workflow with MCP-based tool integrations.

## Features

- ✈️ Flight research using AviationStack (schedules/airlines — not ticket
  prices; AviationStack's free tier has no fare data, so the agent won't
  invent a number)
- 🏨 Hotel suggestions using Tavily search
- 🌤 Weather and multi-day forecast via a custom MCP tool backed by
  Open-Meteo (free, keyless; forecasts follow the trip's actual dates)
- 🧠 Multi-agent orchestration with LangGraph and MCP
- 📝 Structured travel itinerary generation
- 🌐 FastAPI backend with a simple web interface
- 💾 Conversation state persistence using PostgreSQL (pooled connections)
- ⚡ LLM-powered responses with Groq

See `docs/blueprint.md` for the longer-term product plan and
`docs/progress.md` for what's actually been built against it.



## Tech Stack

- Python 3.10+
- FastAPI
- Jinja2 + HTML/CSS/JavaScript frontend
- LangGraph
- LangChain
- Groq LLMs
- PostgreSQL
- Tavily API
- AviationStack API
- MCP via `langchain-mcp-adapters` and `mcp`



## State and MCP Integration

This project integrates MCP in several places:

- `Tavily` search uses a remote MCP endpoint at `https://mcp.tavily.com/mcp/`
- `AviationStack` uses a local stdio MCP command: `uvx aviationstack-mcp`
- `Weather` is implemented with a custom local MCP server in `custom_weather_mcp_server.py`

The MCP client is defined in `mcp_client.py`, which exposes async helper functions for:

- `tavily_mcp_search`
- `aviation_mcp_call`
- `weather_mcp_search`
- `forecast_mcp_search`
- `extract_destination`
- `extract_trip_dates`

The main travel workflow in `backend.py` calls these helpers from the flight, hotel, and weather agents.

## Project Structure

```text
.
├── app.py                      # FastAPI app entry point
├── backend.py                  # LangGraph travel workflow
├── mcp_client.py               # MCP client and tool integration
├── custom_weather_mcp_server.py# Local weather MCP server (Open-Meteo)
├── requirements.txt            # Runtime dependencies
├── requirements-dev.txt        # + ruff/pytest for local dev and CI
├── docker-compose.yml          # Local Postgres for dev
├── static/                     # Static frontend assets
├── templates/                  # HTML templates
├── tools/                      # IATA/airport resolution, used by flight_agent
├── tests/                      # pytest unit tests (no live network/DB)
├── docs/                       # Product blueprint + progress tracking
└── .github/workflows/          # CI (lint + test on push/PR)
```



## Prerequisites

Before running the project locally, make sure you have:

- Python 3.10 or newer installed
- PostgreSQL running and accessible
- API keys for:
  - Groq
  - Tavily
  - AviationStack
- `uv`/`uvx` available for local `aviationstack-mcp` usage — `pip install uv`
  or see [astral.sh/uv](https://astral.sh/uv) (weather no longer needs a key
  or subprocess setup beyond that; it's powered by the free, keyless
  Open-Meteo API)

No Postgres of your own? `docker compose up -d postgres` starts one locally
using `docker-compose.yml` in the repo root.

## Environment Variables

Copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
```

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/travel_db
GROQ_API_KEY=your_groq_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
TAVILY_API_KEY=your_tavily_api_key
DEFAULT_ORIGIN_IATA=DEL
```



## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt        # runtime deps
pip install -r requirements-dev.txt    # + ruff/pytest, for local dev
```

## Testing and linting

```bash
pytest        # unit tests — no live network/DB calls
ruff check .  # lint
```



## Running the App

Start the FastAPI server:

```bash
python app.py
```

Then open your browser at:

```text
http://127.0.0.1:8000/
```



## Using MCP Tools

The app uses MCP behind the scenes, so there is no separate frontend change required after the environment is set up.

If you need to customize the weather MCP server command, edit `mcp_client.py` and update the `weather` tool path to your local Python environment.

## API Endpoints

- GET /health - Health check
- POST /api/travel - Submit a travel request

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/travel \
  -H "Content-Type: application/json" \
  -d '{"message":"Plan a 3-day trip to Tokyo with a budget of $1200"}'
```



## How the Workflow Works

1. The user submits a travel request.
2. The flight agent uses MCP-backed AviationStack data.
3. The hotel agent uses a remote Tavily MCP search.
4. The weather agent calls the custom weather MCP server.
5. The itinerary agent creates a practical travel plan.
6. The final response is returned through the web API.



## Contributing

Contributions are welcome. If you want to improve the app, add new travel features, or fix issues:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Open a pull request



## Acknowledgments

This project is built with the help of modern LLM tooling, MCP integrations, and travel APIs. It is intended as a practical example of combining LangGraph agents with real-world applications.

