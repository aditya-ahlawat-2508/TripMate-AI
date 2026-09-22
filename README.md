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
│   ├── api/           FastAPI + LangGraph backend — see apps/api/README.md
│   │   ├── graph/       Typed planning graph (TripSpec, clarify, fan-out, compose, verify)
│   │   ├── providers/   Flight/stay/weather/places/routing adapters
│   │   ├── models/      Trip/TripSpec/Money/Source (Pydantic)
│   │   └── scripts/     seed_demo_trips.py — zero-cost showcase trips
│   └── web/            Next.js frontend — landing, /plan, /trip/[id]
├── infra/
│   └── docker-compose.yml   Local Postgres + Redis for dev
├── docs/
│   ├── blueprint.md   Condensed product/engineering plan
│   └── progress.md     Actual status against the plan — update every session
└── .github/workflows/  CI (lint + test on push/PR, api + web jobs)
```

## Quick start

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis

cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # fill in GROQ_API_KEY, AVIATIONSTACK_API_KEY, TAVILY_API_KEY
pytest && ruff check .
python app.py           # http://127.0.0.1:8000
python -m scripts.seed_demo_trips   # once, after the app has booted at least once

cd ../web
npm install
npm run build && npm run lint
npm run dev              # http://localhost:3000
```

## Status

Mid-rebuild. Both the legacy conversational planner (`/api/travel`) and a
new typed planning graph (`/api/plan` — TripSpec intake, HITL clarify,
parallel provider fan-out, a structured composer, and a deterministic
verifier with a repair loop) run side by side. Weather and places use real,
keyless data (Open-Meteo, OpenStreetMap); flights/stays have working
adapter code gated on `DUFFEL_API_KEY`/`LITEAPI_KEY` that nobody has tested
against a live key yet. The Next.js frontend covers landing → plan → share,
without auth, payments, or a real trips dashboard. See `docs/progress.md`
for the authoritative, detailed status and what's still genuinely blocked
on the project owner creating accounts (Duffel, LiteAPI, Clerk, Razorpay,
PostHog, Sentry, Langfuse).
