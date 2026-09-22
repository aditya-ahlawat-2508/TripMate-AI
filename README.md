# TripMate AI

An AI trip planner being rebuilt from a LangGraph/MCP portfolio project into
a budget-true, India-first SaaS: real fares and room rates (sourced,
timestamped), a structured/editable trip plan on a map and timeline, and
one-click booking/sharing. See [`docs/blueprint.md`](docs/blueprint.md) for
the full product plan and [`docs/progress.md`](docs/progress.md) for what's
actually built so far.

## Layout

```text
.
├── apps/
│   └── api/          FastAPI + LangGraph backend — see apps/api/README.md
│                      (apps/web/, the Next.js frontend, doesn't exist yet)
├── infra/
│   └── docker-compose.yml   Local Postgres for dev
├── docs/
│   ├── blueprint.md   Condensed product/engineering plan
│   └── progress.md     Actual status against the plan — update every session
└── .github/workflows/  CI (lint + test on push/PR, scoped to apps/api)
```

## Quick start (current backend only)

```bash
docker compose -f infra/docker-compose.yml up -d postgres
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # fill in GROQ_API_KEY, AVIATIONSTACK_API_KEY, TAVILY_API_KEY
pytest && ruff check .
python app.py           # http://127.0.0.1:8000
```

## Status

This is mid-rebuild. The backend (`apps/api/`) is a stabilized version of
the original single-service app — real dated weather forecasts, deterministic
flight-route resolution, no invented fares, pooled DB connections, tested and
in CI. The typed LangGraph rewrite (TripSpec, parallel fan-out, verifier),
the Next.js frontend, real fare/hotel/places data, and auth/payments are not
built yet. See `docs/progress.md` for the authoritative, up-to-date status.
