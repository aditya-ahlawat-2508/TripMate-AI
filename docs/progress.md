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
- **Flights** (`flights.py`): `DuffelFlightProvider`, **verified working
  end-to-end against a real Duffel test-mode key** (2026-09-23) — real
  offers, real airlines, for a DEL→GOA route. One real bug found in the
  process, now fixed (see "Duffel verification" below).
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

## Duffel verification (2026-09-23)

Project owner got a Duffel test-mode key (`DUFFEL_API_KEY` in
`apps/api/.env`, never committed). `DuffelFlightProvider.search()` works
on the first real call — 10 offers, real airline names (British Airways,
Iberia, plus Duffel's own test airline), plausible schedule/duration data
for a DEL→GOA search.

**One real bug found and fixed by this**: Duffel's sandbox returns fares
in **EUR** regardless of route or origin — not the INR `TripSpec.budget`
defaults to. `compose.py:_compute_budget` was summing every slot's
`Money.amount_minor` regardless of currency, which would have silently
produced a meaningless total the moment a EUR flight sat next to an INR
stay. Fixed: the budget total only includes slots matching the trip's
own currency; anything else is excluded from the sum and surfaces as an
explicit warning (`'Flight: ...' is priced in EUR, not INR — excluded
from the budget total`) instead of being silently mixed in or dropped.
No FX conversion is wired up — blueprint §05 already flags this as a
real, not-yet-built need. 4 new unit tests in `test_compose.py`, plus
live end-to-end confirmation the warning shows up correctly through the
real API.

`LiteAPIStayProvider` is still a stub — no LiteAPI key yet.

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

## Phase 5 — SaaS foundations (done: 2026-09-23, partial by design)

Project owner provided real test-mode/sandbox keys for Clerk, Razorpay,
Langfuse, and PostHog (2026-09-23) — all wired in and where possible,
live-verified rather than just written against docs.

**Langfuse** (`observability.py`): `get_langfuse_callbacks()` returns a
`CallbackHandler` (empty list if unconfigured — never breaks a call).
Wired into both LLM call sites in the typed graph (`graph/intake.py`,
`graph/compose.py` — `config={"callbacks": ...}`). **Verified live**:
`Langfuse().auth_check()` returned `True` and a manual trace was sent
successfully. The actual LangChain-integration traces (from real
`intake`/`compose` calls) aren't yet visible in the dashboard, because
`GROQ_API_KEY` is still a placeholder — nothing has called through the
LangChain callback path for real yet. Not wired into the legacy
`backend.py` graph (lower priority; that graph is being phased out).

**Clerk** (`auth.py`, `apps/web` `middleware.ts`→`proxy.ts`): JWT
verification via `PyJWKClient` against Clerk's public JWKS — no Clerk
Python SDK dependency. `CLERK_ISSUER` is the Frontend API host decoded
from the publishable key's base64 payload. **Verified**: JWKS endpoint
fetches real signing keys live; 9 unit tests exercise the full
verify/reject path with a self-signed RSA keypair (valid signature
accepted, wrong key rejected, wrong issuer rejected — not just "does it
parse"). `get_current_user_id` (optional, never raises) vs
`require_user_id` (401s) as separate FastAPI dependencies, matching
where auth should be optional (`/api/plan`, still works anonymously) vs
required (`/api/trips`, `/api/billing/*`).

This is the actual fix for the audit's Critical IDOR item:
`trips_store.py` got a nullable `owner_id` column (migrated
idempotently via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, so an
already-running deployment picks it up without a manual step); `/api/plan`
attaches the signed-in user's ID when present; `GET /api/trips` (new)
returns only that user's own trips and 401s otherwise — verified live
(unauthenticated request → 401).

Frontend: `ClerkProvider` wraps the root layout; `SiteHeader` (new,
replaces the ad-hoc headers on the landing/trip-workspace pages) shows
sign-in or a user menu + "My Trips"/"Billing" links. **Real bug found and
fixed**: `@clerk/nextjs`'s newest major version ("Core 3") removed
`<SignedIn>`/`<SignedOut>`/`<Protect>` entirely — they now throw on
render by design, pointing at a migration doc. `SiteHeader` was rewritten
to use `useAuth()`'s `isLoaded`/`isSignedIn` instead. Also needed
`CLERK_SECRET_KEY` set in **both** `apps/api/.env` and
`apps/web/.env.local` — they're separate processes that don't share
environment variables, which wasn't obvious until the dev server actually
threw "Missing secretKey" at runtime.

`app/trips/page.tsx` (new): server component, redirects to `/` if signed
out, otherwise lists the user's trips via `GET /api/trips`. **Not
verified**: the actual interactive sign-in flow (Clerk's modal, a real
session, a token round-tripping to the backend) — no headless browser
available this pass. Verified instead: unauthenticated `/trips` and
`/billing` both 307-redirect correctly (proves the route-level auth
gating works); the JWT verification logic itself is fully tested (above).

**Razorpay** (`payments.py`, `subscriptions_store.py`): `create_pro_order()`
**verified live** — created a real order (`order_TfOx58M4jd32ba`) against
Razorpay's test-mode API with the real amount/currency/notes. Webhook
signature verification (`verify_webhook_signature`) is unit-tested against
real HMAC-SHA256 signing (accepts valid, rejects wrong signature, rejects
a tampered body) but **not exercised against an actual webhook delivery**
— that needs `RAZORPAY_WEBHOOK_SECRET` from a webhook configured in the
Razorpay dashboard pointing at a publicly reachable URL, which doesn't
exist yet (no deployment). Until then, `POST /api/billing/webhook`
correctly fails closed (400) rather than trusting an unsigned/unconfigured
request. `subscriptions` table (owner_id, plan, status,
razorpay_order_id/payment_id) mirrors blueprint §08's data model.
`POST /api/billing/create-order` (401 if signed out — verified live) and
`GET /api/billing/status` round out the API; `app/billing/page.tsx` +
`components/upgrade-button.tsx` open Razorpay's real Checkout.js modal.
Pro plan priced at ₹249/mo (blueprint's own ₹199-299 range, picked as a
starting midpoint — still an unvalidated hypothesis per blueprint §03).

**PostHog** (`components/posthog-provider.tsx`): client-side init,
manual `$pageview` capture (so App Router client-navigations get tracked,
not just full loads), plus three funnel events from blueprint §08's
"landing → wizard → plan → share → booking click": `plan_started`
(landing page form submit), `trip_completed` (graph returns a finished
Trip), `trip_shared` (share-link copy click). Not verified live (would
need a real browser session hitting PostHog's ingestion API) — the
initialization code path is straightforward and matches PostHog's
documented Next.js App Router pattern.

**Sentry**: explicitly skipped per project owner's instruction this
session.

## Phase 6 — Real Groq key + real browser verification (done: 2026-09-23)

Project owner provided a real `GROQ_API_KEY`. This was the last major
unverified assumption in the typed graph, and testing it end-to-end
immediately surfaced two 100%-failure-rate bugs that the mocked test
suite could never have caught (mocks assume well-formed LLM output —
these were about Groq's *strict tool-schema validation* rejecting
otherwise-correct output):

1. `PlannedSlot.start`/`end` were `datetime.time`. Groq's schema
   validator wants `"HH:MM:SS"` for a time-formatted string; the model
   naturally emits `"HH:MM"` (`"08:00"`) — every composer call failed
   validation and silently fell back to an empty itinerary. Fixed:
   `start`/`end` are now plain strings parsed leniently by
   `_parse_time()` (tries `HH:MM:SS` then `HH:MM`, falls back to a sane
   default rather than crashing).
2. `TripSpec.interests`/`constraints` were bare `list[str]`. When the
   model has nothing to put there it emits `null`, not `[]` — rejected
   by a plain `"type": "array"` schema, failing every intake call that
   didn't explicitly state interests/constraints. Fixed: both fields are
   `list[str] | None` (schema permits null) with a
   `@model_validator(mode="after")` normalizing `None` back to `[]`.

Also extended the intake prompt to compute `date_end` from a stated trip
length ("2 day trip" + a start date) instead of leaving it null.

**Verified end-to-end with real everything** (Groq, Duffel, Open-Meteo,
Overpass): "Plan a 2 day trip from Delhi to Goa starting 2026-11-15 for
2 travelers, budget 30000 rupees, relaxed pace, interested in beaches"
now produces a real, sensible 2-day itinerary — real beaches (Calangute,
Baga, Anjuna), real restaurants, real per-day weather, a real flight,
and a budget that correctly excludes the EUR-priced flight with a clear
warning rather than corrupting the total. Confirmed via Langfuse's API
that real `intake`/`compose` traces are landing (had to use
`GET /api/public/v2/observations` — the v1 traces endpoint is retired
for organizations created after 2026-09-16, also learned live).

**Real browser verification**: found real Chrome already installed
(`/Applications/Google Chrome.app`) and drove it headlessly via
Playwright's `channel: "chrome"` — no Chromium download needed. Full
anonymous flow exercised end-to-end: landing page → fill the plan form →
`/plan` → real clarify-free completion (all fields given upfront) →
redirect to `/trip/[id]` → verified 2 day tabs, a real budget panel, and
screenshotted both the landing page and the finished trip workspace.
**The trip workspace screenshot is genuinely good** — clean layout, real
sourced data throughout, the SVG map correctly plots and connects the
day's located slots, warnings banner reads clearly. This is the first
time any of this session's frontend work has been confirmed to actually
render correctly in a browser rather than just type-check and build.

**Real bug found this way**: the PostHog key the project owner provided
(`phs_...`) 404s against PostHog's config endpoint —
`us-assets.i.posthog.com/array/phs_.../config` returns 404, meaning
PostHog analytics is **not actually capturing events** even though the
integration code is correct. PostHog's client-tracking project keys
normally start with `phc_`, not `phs_` — this looks like the wrong key
was copied from the dashboard (a personal/other API key, not the
"Project API Key" used for `posthog.init()`). Not something more code
can fix; needs the project owner to grab the right key.

## What's still genuinely blocked (needs the project owner, not more code)

- **LiteAPI** (`LITEAPI_KEY`) — sign up at liteapi.travel, implement
  `LiteAPIStayProvider.search()` (currently a stub).
- **The right PostHog key** — see above; current one 404s.
- **Sentry** — skipped this session by explicit instruction.
- **Razorpay webhook** — needs a publicly reachable URL (a real
  deployment) to configure the webhook and get `RAZORPAY_WEBHOOK_SECRET`;
  can't be done from localhost.
- Indian rail/bus data — needs an IRCTC-authorised partner or bus
  aggregator affiliate deal; no free keyless equivalent exists. Skipped
  this session by explicit instruction.
- Production deployment (needed for: the Razorpay webhook above, a real
  Clerk sign-in test with a real user account, a custom domain, uptime
  monitoring).
- A real Tavily key — still a placeholder, so hotel search/stays are
  never populated (confirmed live: `tavily-search` 401s every time).

## Next session should start with

1. Golden-set eval suite (blueprint §09) — now the highest-value next
   piece, and fully buildable/testable with what's already live-verified
   (real Groq, Duffel, weather, places): "0 unsourced prices, 0
   wrong-city places" is the actual launch-gate metric and has no
   automated check yet beyond the unit/graph tests.
2. LiteAPI and a real Tavily key, once available — same pattern as
   Duffel: implement/fix, verify live.
3. The right PostHog key.
4. A real Clerk sign-in test (needs an actual user account, not just
   route-level auth checks) — everything up to that point (JWKS
   verification, route gating, 401s) is now verified; the interactive
   sign-in modal itself still isn't.
