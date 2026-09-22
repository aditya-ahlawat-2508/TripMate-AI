# Progress

Tracks actual status against `docs/blueprint.md`. Update at the end of each
work session.

## Phase 0/1 — Stabilize the existing single-service app (done: 2026-09-23)

Scope: fix real, well-defined bugs in the *current* Python app without
requiring any new paid-provider signups or architecture decisions. Did
**not** attempt the monorepo/Next.js rewrite — that's Phase 2+ and needs the
decisions logged below first.

Done:
- Weather rewritten on Open-Meteo: real daily forecast for the actual trip
  dates (extracted from the user's message via a small LLM call), historical
  average fallback beyond the ~16-day forecast horizon. No more "next 15
  hours" bug, no API key required.
- `flight_agent` now resolves departure/arrival airports deterministically
  via `tools/flight_tool.py`'s `parse_route`/`resolve_location_to_iata`
  instead of dumping a truncated, arbitrary slice of the full airport list
  at the LLM. The prompt also explicitly forbids inventing a fare number.
- Fixed a real bug in `resolve_location_to_iata`'s fuzzy city matching
  (the "international airport" score bonus applied even with no actual
  match, so unresolvable input silently returned a real but wrong airport).
  Found because this code is now load-bearing in the live path.
- Connection pooling: `AsyncConnectionPool` instead of one shared
  `AsyncConnection`, so concurrent requests don't serialize.
- `get_database_url()` only force-appends `sslmode=require` for non-local
  hosts, so local Postgres works.
- Tavily MCP auth moved from a URL query string to an `Authorization`
  header (confirmed supported per Tavily's docs) — the key no longer lands
  in proxy/server logs.
- MCP tool lookups raise a clear `RuntimeError` listing available tools
  instead of a bare `StopIteration` when an upstream tool is renamed.
- `/api/travel` returns a generic message + error ID to the client;
  the real exception is logged server-side instead of echoed to the browser.
- Dockerfile now installs `uv` (copied from its official image) so
  `uvx aviationstack-mcp` can actually start in the container.
- Dead code removed: `mcp_client_test.py`, `tools/tavily_tool.py`.
  `tools/flight_tool.py` kept and is now actively imported by `backend.py`.
- `.env.example` added; `OPENWEATHER_API_KEY` dropped from it (no longer
  needed — Open-Meteo is keyless).
- Test suite added (`tests/`, 26 tests, pure-function/unit level, no live
  network or DB calls) + `ruff` config + GitHub Actions CI running lint +
  tests on push/PR to `main`.
- `docker-compose.yml` added for local Postgres (dev convenience).
- `CLAUDE.md` untracked per explicit request — it's gitignored and stays
  local-only from now on, not pushed to GitHub.

Still open in the current architecture (not attempted this pass — each
needs either a provider decision or the Phase 2 auth/typed-graph work):
- Flight fares are still not real prices (needs a fare API decision —
  Duffel/Ignav/Travelpayouts).
- No auth yet, so the `thread_id` IDOR issue and rate limiting/quotas are
  still open — this is real Phase 2/5 work, not a quick patch.
- `itinerary_agent` + `final_agent` still both re-write the whole trip
  (two large LLM calls); the real fix is the typed composer + verifier
  graph from blueprint Section 4.
- Hotels are still raw Tavily web snippets, not structured/sourced rates.

## Decisions (2026-09-23)

Asked the project owner at the end of the Phase 0/1 session:
- **Scope**: commit to the full SaaS rebuild now (not pausing at the
  stabilized single-service app).
- **Flight fares**: Duffel, once Phase 3 (real data) starts. Needs the
  owner to sign up and drop a key in `apps/api/.env` — not something this
  session can do on its own.
- **Auth**: Clerk, once Phase 2's auth work starts.

## Phase 0 — Monorepo split (done: 2026-09-23)

Moved the stabilized single-service app into the blueprint's target layout
without changing its behavior:
- `apps/api/`: all Python source, `tests/`, `tools/`, `static/`,
  `templates/`, `Dockerfile`, `.dockerignore`, `.env.example`,
  `pyproject.toml`, `requirements*.txt`. Re-verified end-to-end after the
  move (pytest, ruff, and a live local-Postgres run of
  `build_travel_graph()` + `/health` through the FastAPI lifespan) —
  nothing broke.
- `infra/docker-compose.yml`: moved from the repo root.
- `apps/web/`: scaffolded with `create-next-app` (TypeScript, Tailwind,
  App Router, ESLint) per the blueprint's frontend stack choice. Default
  boilerplate page replaced with a placeholder; `npm run lint` and
  `npm run build` both pass. **shadcn/ui, TanStack Query, Framer Motion,
  Mapbox/MapLibre, dnd-kit, react-hook-form+zod are not installed yet** —
  intentionally deferred to Phase 4 (actual UI work) rather than adding
  dependencies with nothing using them yet.
- CI (`.github/workflows/ci.yml`) split into an `api` job
  (`ruff check` + `pytest`, scoped to `apps/api`) and a `web` job
  (`npm run lint` + `npm run build`, scoped to `apps/web`).
- Root `README.md` rewritten as a short monorepo overview; the old
  Python-specific content moved to `apps/api/README.md` with paths fixed.
- `graph/`, `providers/`, `models/`, `workers/`, `packages/api-client/`,
  `evals/` from the blueprint's target layout **do not exist yet** — they
  get created when Phase 2/3/4 actually need them, not as empty
  placeholders now.

## Phase 2+ — not started

Typed TripSpec/Send-API graph rewrite (Phase 2), real data providers —
Duffel for fares, still need to pick a stays/places/routing provider
(Phase 3), the actual Next.js UI (Phase 4), Clerk auth + Razorpay/Stripe
payments (Phase 5), and launch prep (Phase 6) are all still just the plan,
not code. Given the invasiveness of Phase 2 in particular (HITL
`interrupt()`, parallel fan-out via the Send API, and a verifier node all
rework the currently-working conversational graph), the next session should
open with a concrete Phase 2 plan for review before writing that code —
per the blueprint's own build methodology ("start each phase by asking for
a plan and reviewing it before any code is written").
