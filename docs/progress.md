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

## Phase 2 — Typed planning graph (done: 2026-09-23)

`apps/api/models/` (Pydantic): `Money`, `Source`, `TripSpec`, `FlightOffer`,
`StayOffer`, `DayWeather`, `Place`, `GroundOption`, `Slot`, `Day`,
`BudgetBreakdown`, `Trip` — matches blueprint §04's schema plus explicit
`Source` on every offer type.

`apps/api/graph/` (new, additive — the old 5-node graph in `backend.py`
is untouched and still serves `/api/travel`):
- `intake.py`: structured-output TripSpec extraction (`llm.with_structured_output`),
  falls back to an empty spec (triggering clarify) if the LLM call fails.
- `clarify.py`: `interrupt()`-based HITL, one missing field per pause
  (origin → destination → date_start), replacing free-text `extract_destination()`.
- `fanout.py`: flights/stays/weather/places/ground nodes, each wrapping
  its provider(s) in `providers.base.call_provider` so a failure becomes a
  warning, never a crash or invented data.
- `compose.py`: one structured-output call constrained to real place IDs
  and forbidden from stating any price; Python then builds `Day`/`Slot`
  objects and computes the budget total purely from typed `FlightOffer`/
  `StayOffer` money — the LLM never touches a number.
- `verify.py`: **deterministic** checks (sourced-price, daily-hours,
  geography-via-haversine-distance) — deliberately not the blueprint's
  suggested "cheap LLM check", since a distance calculation is more
  reliable and directly unit-testable. Repair loop, max 2 attempts, then
  finalizes with warnings rather than looping forever.
- `graph.py`: fan-out via a conditional edge returning a list of node
  names, not the Send API — Send is for a dynamic/unknown-size branch set
  (map-reduce); ours is a fixed 5 branches, so a conditional multi-target
  edge is the simpler mechanism for the same effect. Verified this works
  with a throwaway test graph before committing to the design.

New endpoints in `app.py`: `POST /api/plan` (message or `resume_answer`;
returns `needs_input`+question or `done`+typed `Trip` JSON) and
`GET /api/plan/{trip_id}`. Server-generated `Trip.id`/`thread_id` (UUIDs),
not client-supplied — narrows (doesn't fully close; that needs auth) the
old thread_id IDOR issue.

**Testing**: 24 new graph/verify tests with mocked providers and a fake
structured-output LLM (per blueprint §11 Phase 2's own acceptance
criterion), covering: full happy path + JSON-schema round-trip, HITL
interrupt-then-resume, hallucinated place_id dropped, repair loop actually
advancing (caught and fixed a real bug in the test fakes where a
fresh-per-call fake LLM silently defeated the repair-loop test), repair
budget exhaustion terminates cleanly, provider failure surfaces as a
warning not a crash.

## Phase 3 — Real data providers (done: 2026-09-23, partial by design)

`apps/api/providers/`:
- **Weather** (`weather.py`): real, keyless, wraps the existing Open-Meteo
  MCP integration.
- **Places** (`places.py`): real, keyless — OpenStreetMap via the public
  Overpass API. Not for production volume (shared public instance); swap
  for self-hosted Overpass or Google Places before launch traffic.
- **Ground transport** (`routing.py`): real, keyless — OSRM's public demo
  server for an origin→destination driving estimate. Same "not for
  production volume" caveat. Rail/bus stays unavailable — no free keyless
  Indian rail/bus API exists; needs the IRCTC/bus-aggregator partnership
  blueprint §05 already flagged as a manual step.
- **Flights** (`flights.py`): `DuffelFlightProvider` implemented against
  Duffel's public v2 Offer Requests API docs, gated on `DUFFEL_API_KEY`.
  **Untested against a live key** — none was available. Wrapped by
  `call_provider`, so a wrong request/response shape surfaces as a
  warning, not a crash. First thing to verify once a real key exists.
- **Stays** (`stays.py`): `LiteAPIStayProvider` stub (same honesty pattern
  as Duffel, gated on `LITEAPI_KEY`, not implemented). Falls back to
  `TavilyStaySearchProvider` — hotel *names and links* from the existing
  Tavily integration, `price_per_night` always `None` since Tavily has no
  real rate data.
- **Cache** (`cache.py`): Redis get/set helpers, fails open (a Redis
  outage degrades to "call the provider live", never breaks the request).
  Redis added to `infra/docker-compose.yml`. **Not yet wired into any
  provider call site** — the plumbing exists, the actual caching-decorator
  integration is still open.

**Two real bugs found and fixed while live-testing against the free
providers** (not caught by mocked tests, since the mocks assumed
well-formed responses):
1. `MultiServerMCPClient.get_tools()` with no `server_name` connects to
   *every* configured MCP server at once — a broken Tavily key (401) was
   taking down weather and aviation tool lookups too, via one shared
   exception. Fixed in `mcp_client.py`: each of `initialize_search_tool()`
   / `initialize_aviation_tools()` / `initialize_weather_tools()` now
   scopes its `get_tools(server_name=...)` call to just its own server.
2. Open-Meteo's free geocoder resolves "Goa" to a 21k-person town in the
   Philippines before India's Goa (which isn't even indexed as a
   top-level "city" there) — "Panaji" fuzzy-matches a village in
   Guatemala. Since TripMate is explicitly India-first (blueprint §03),
   added a curated `KNOWN_LOCATIONS` override table in
   `custom_weather_mcp_server.py` for ~20 major Indian
   destinations/metros, checked before falling back to the API. This is a
   real, disclosed limitation for any destination *not* on that list —
   the free geocoder's ranking isn't relevance-aware, and a proper fix
   needs a paid/better geocoder (Google Geocoding, Mapbox) or a much
   larger curated table.

Also fixed while live-testing: `langchain-mcp-adapters` returns tool
output as a list of MCP content blocks (`[{"type": "text", "text":
"<json>"}]`), not the tool's return value directly — the weather and
stays providers were silently getting `[]` back from well-formed
responses until `_unwrap_mcp_result`/`_extract_items` were taught to
parse that shape. And a `psycopg` `dict_row` gotcha in `trips_store.py`:
jsonb columns come back already decoded as a Python dict, not a JSON
string — `Trip.model_validate_json()` was the wrong call.

**Redis caching, provider-level contract fixtures beyond what's in
`tests/test_providers.py`, and a golden-set eval suite (blueprint §09)
are still open** — the "0 unsourced prices, 0 wrong-city places" launch
gate has no automated check yet beyond the unit/graph tests.

**Demo mode** (`apps/api/scripts/seed_demo_trips.py`, `GET
/api/demo-trips`): 2 hand-built showcase trips (Goa, Manali) with real
place coordinates, seeded into the `trips` table with `is_demo=true` and
`Source(provider="demo-seed", ...)` — never claimed as live prices,
servable with zero API cost per blueprint's demo-mode spec. Run
`python -m scripts.seed_demo_trips` from `apps/api/` after
`ensure_trips_table` has run once (i.e. after the app has booted at least
once, or call it directly).

## Phase 4 — Web app (done: 2026-09-23, partial by design)

`apps/web/`: landing page (server component, fetches `/api/demo-trips`
live), `/plan` (client-side chat-style flow driving `POST /api/plan`'s
clarify loop), `/trip/[id]` (server component — doubles as the share
page; also used for demo trips). Typed API client in `lib/api.ts` +
hand-written types in `lib/types.ts` mirroring the Pydantic models —
blueprint §07 specifies a client generated from the FastAPI OpenAPI
schema; that's the right long-term move, hand-typing was faster to ship
correctly without setting up a codegen pipeline this pass.

**Deliberately not installed**: shadcn/ui, TanStack Query, Framer Motion,
Mapbox GL/MapLibre, dnd-kit, react-hook-form+zod. The map panel is a
small dependency-free SVG scatter-plot of each day's slot coordinates
(`components/slot-map.tsx`) instead of a real tile-based MapLibre map —
it's real and synced with the timeline, just not a basemap. The
onboarding flow is a single free-text input, not the 4-step wizard with
sliders from blueprint §09's screen inventory, since the clarify loop
already collects the structured fields conversationally.

**Verified**: `npm run build` and `npm run lint` both clean. Landing page
and `/trip/[id]` verified server-side via curl against a live backend —
demo trip cards render with real fetched data, a seeded Goa trip's real
slot titles/prices render correctly, an unknown trip ID 404s to a real
not-found page. **Not verified**: the interactive `/plan` client flow
(clarify Q&A) was not exercised in an actual browser — no headless
browser was set up this pass, so this is confirmed only at the API layer
(curl, see Phase 2 above) and via TypeScript/lint on the component code.
Trips dashboard, alerts, and settings/billing screens from blueprint
§07's screen inventory don't exist — they need auth (Phase 5) to mean
anything (whose trips would a dashboard list?).

## What's still genuinely blocked (needs the project owner, not more code)

- **Duffel** (`DUFFEL_API_KEY`) — sign up at duffel.com, verify
  `DuffelFlightProvider` against a real response, fix whatever's wrong.
- **LiteAPI** (`LITEAPI_KEY`) — sign up at liteapi.travel, implement
  `LiteAPIStayProvider.search()` (currently a stub).
- **Clerk** — sign up, wire into `apps/web` (middleware, sign-in/up
  pages) and verify JWTs in a FastAPI dependency. Everything downstream
  of auth (per-user trip ownership, quotas, rate limiting, the real IDOR
  fix, a trips dashboard) is blocked on this.
- **Razorpay** — sign up, webhook → subscriptions table → entitlements.
- **PostHog / Sentry / Langfuse** — sign up for each; none of this
  session's code emits to them yet.
- Indian rail/bus data — needs an IRCTC-authorised partner or bus
  aggregator affiliate deal; no free keyless equivalent exists.

## Next session should start with

1. Run `python -m scripts.seed_demo_trips` (needs `ensure_trips_table` to
   have run at least once — start the app once first) and sanity-check
   `/api/demo-trips` + the landing page.
2. Decide: keep building Phase 5 (SaaS foundations) now, or pause to
   actually get Duffel/LiteAPI/Clerk keys first so Phase 3/5 code can be
   verified against real responses instead of shipped untested.
3. If continuing without those keys: golden-set eval suite (blueprint
   §09) is the highest-value next piece — it's buildable and testable
   entirely with the free/keyless providers already wired up, and is the
   actual launch-gate metric ("0 unsourced prices, 0 wrong-city places").
