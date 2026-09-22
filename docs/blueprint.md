# TripMate AI — SaaS Blueprint (condensed)

Source: `TripMate_AI_SaaS_Blueprint.pdf`, prepared September 2026. This file
condenses that document into something cheap for future sessions to re-read.
It is the long-term product/engineering plan; `docs/progress.md` tracks what
has actually been done against it.

## 1. Product thesis

TripMate only wins if:
1. Every number on screen is **sourced** (real fare, real room rate, real
   opening time) with a timestamp.
2. The plan is a **structured, editable object** (days → slots → places with
   lat/lng, cost, booking link) — not a markdown blob.
3. The user can **book or share it in one click**.

Chosen wedge: **budget-true, India-first planner** (hard INR budget, live
fares/trains/buses/stays) as the core promise, with **group trip planning**
as the first growth/viral feature. B2B white-label is a later revenue line.

Monetization: Free tier (3 plans/month) + Pro subscription (₹199–299/mo) +
affiliate commissions on flights/hotels/activities (likely the largest
revenue line early on). Figures are hypotheses to validate with 20–30 users,
not researched benchmarks.

## 2. Code audit — status

The original audit (see the PDF, section 02) listed these issues. Status
reflects the actual repo as of the Phase 0/1 pass, not the PDF's claims:

| Sev. | Issue | Status |
|---|---|---|
| Critical | Flight fares invented by the LLM | Partially mitigated: prompt now forbids inventing a number; a real fare source (Duffel etc.) is still needed for actual prices — **blocked on picking a provider** |
| Critical | Weather forecast was next-15-hours, ignored trip dates | **Fixed** — rewritten on Open-Meteo, daily forecast keyed by real trip dates, historical-average fallback beyond the 16-day horizon |
| Critical | Any client can pass any `thread_id` (IDOR) | **Still open** — needs auth; there's no user concept yet at all |
| High | Docker image runs `uvx` without installing `uv` | **Fixed** — `uv` copied into the image from its official image |
| High | Single shared `AsyncConnection` serializes concurrent requests | **Fixed** — `AsyncConnectionPool` |
| High | `DEFAULT_ORIGIN_IATA` leftover tutorial default | **Still open by design** — proper fix is structured intake (Section 4 below), not a bigger default table |
| High | No auth, no rate limiting, no request size cap | **Still open** — needs an auth/hosting decision |
| Medium | Tavily key in MCP URL query string (logs) | **Fixed** — moved to an `Authorization` header |
| Medium | Exceptions returned to browser verbatim | **Fixed** — generic message + error ID, real detail logged server-side |
| Medium | Bare `StopIteration` on renamed MCP tool | **Fixed** — explicit `find_tool()` helper with a clear error |
| Medium | `itinerary_agent` + `final_agent` both re-write the whole trip | **Still open** — real fix is the typed composer in Section 4 |
| Low | Dead code (`tools/`, `mcp_client_test.py`) + stale `CLAUDE.md` | `mcp_client_test.py` and `tools/tavily_tool.py` deleted; `tools/flight_tool.py` kept and now actively used for IATA resolution in `flight_agent` |

Two bugs found *while* wiring `flight_tool.py` into the live path (not in
the original audit): the city-name fuzzy-match scoring let the
"international airport" bonus apply even with zero real match, so any
unresolvable location silently resolved to a real (wrong) airport instead of
`None`; and the module raised at import time if `AVIATIONSTACK_API_KEY`
wasn't set, which would have broken reuse of its pure IATA functions. Both
fixed.

## 3. Product definition

Core jobs to be done: **Decide** (destination discovery under a budget),
**Plan** (day-by-day respecting opening hours/travel time/weather),
**Price** (a total that adds up in code, sourced), **Book & share**.

## 4. AI system redesign (not yet built)

Replace the linear 5-node chain with:

```
User message → Intake parser (→ TripSpec, Pydantic)
             → Clarify (HITL, interrupt() if a required field is missing)
             → Destination picker (only if "suggest a place")
             → parallel fan-out (Send API): Flights, Stays, Weather, Places, Ground
             → Itinerary composer (one structured-output call → Trip JSON)
             → Verifier (prices sourced? budget sums? feasible times?)
             → repair loop (max 2) → stream to UI
```

Key decisions: TripSpec first (replaces free-text destination extraction);
independent lookups run in parallel; every price object carries
`source, fetched_at, currency, deep_link`; budget math and scheduling happen
in Python, never in the model; a verifier node blocks unsourced prices;
fast model for intake, stronger model only for the composer; edits re-run
only the affected slot, not the whole trip.

The `Trip` object (Pydantic): `Trip { id, spec, flights, stays, days, budget,
warnings, version }`, `Day { date, weather, slots }`, `Slot { start, end,
kind, place_id, title, lat, lng, cost, source, notes }`. See the PDF for the
full class definitions.

## 5. Data layer (not yet built)

| Need | Current | Options | Note |
|---|---|---|---|
| Flight fares | AviationStack (schedules only) | Duffel, Ignav, Travelpayouts | Amadeus's free self-serve portal was decommissioned 2026-07-17 — don't design around it |
| Stays | Tavily web snippets | LiteAPI, Booking.com/Agoda affiliate, Travelpayouts | Need room rate, rating, lat/lng, deep link |
| Places/POIs | None | Google Places API (New), Foursquare, OSM/Overpass | Opening hours + coordinates make the itinerary feasible |
| Routing & times | None | Google Routes/Distance Matrix, OSRM/OpenRouteService | Feeds feasibility checks |
| Weather | Open-Meteo (**fixed**) | — | Trips >2 weeks out show historical typical conditions |
| Rail/bus (India) | None | IRCTC-authorised partners, bus aggregator affiliates | Check licensing |
| FX | None | Any daily feed, cached | Store money as `(amount_minor, currency)` |

Caching: Redis, short TTL for fares, long TTL for POIs. Provider adapter
interface (`FlightProvider.search(spec) -> list[FlightOffer]`) so vendors
can be swapped and mocked in tests. Circuit breakers + timeouts per
provider — a failed provider shows a visible warning, never invented data.

## 6. Feature roadmap

- **MVP**: sign-in, onboarding wizard, streamed planning, trip workspace
  (timeline + map), live fares/stays with deep links, budget panel, slot
  regeneration, share link, dashboard, free-tier quota.
- **v1** (+4–6 wks): drag-and-drop reorder, "suggest destinations under ₹X",
  price-drop alerts, PDF/.ics export, packing list, Pro plan + payments.
- **v2** (group): invite friends, vote, comments, expense split, presence.
- **v3**: PWA offline, on-trip re-planning, local transport, multi-city,
  agency white-label.
- **Skip early**: own booking/ticketing flow, social feed/marketplace,
  native mobile apps.

## 7. UI/UX (not yet built)

Frontend stack: Next.js (App Router) + TypeScript, Tailwind + shadcn/ui,
Framer Motion, Mapbox GL/MapLibre, TanStack Query with a typed client
generated from the FastAPI OpenAPI schema, dnd-kit, react-hook-form + zod.

Palette: deep teal primary `#0D9488`, coral accent `#F97316`, full dark
mode. Screens: landing, onboarding wizard, planning view (live step list),
trip workspace (chat + timeline + map + budget), trips dashboard, public
share page, alerts, settings/billing. Quality bar: Lighthouse 90+, 360px
responsive, WCAG AA, every loading state has a skeleton, every error a
retry.

## 8. SaaS foundations (not yet built)

Auth: Clerk/Supabase Auth/Auth.js, JWT verified in a FastAPI dependency,
`user_id` on every query. Data model: `users, trips(owner_id, spec JSONB,
version), trip_versions, trip_members, price_snapshots, alerts,
usage_events, subscriptions`. Payments: Razorpay (India) / Stripe
(international), webhook → subscriptions → entitlements. Quotas: per-user
plan limits, per-IP rate limit, max message length. Background jobs: arq/
Celery/Dramatiq on Redis, progress via SSE. Observability: LangSmith/
Langfuse for traces + cost/plan, Sentry for errors. Deploy: frontend on
Vercel, API/workers as containers, managed Postgres + Redis.

## 9. Testing and evals (partially built)

Unit tests for pure functions exist (`tests/`). Still needed: provider
contract tests against recorded fixtures (no live calls in CI), LangGraph
tests with mocked providers, a 50–100 golden-trip eval set checking "no
unsourced price, right city, feasible days, budget respected", Playwright
E2E, load testing. **Launch gate: zero unsourced prices and zero
wrong-city places across a full golden-set run before any public launch.**

## 10. Execution plan (original 12-week estimate)

Weeks 1–2 stabilize backend (this Phase 0/1 pass); 3–4 real data + verifier;
5–7 Next.js app; 8–9 share/exports/analytics; 10–11 payments + alerts +
load test; 12 public launch. See `docs/progress.md` for actual status.

## 11. Repository target layout (once the monorepo split happens)

```
tripmate/
  apps/web/            Next.js + Tailwind + shadcn/ui frontend
  apps/api/             FastAPI app (routes, auth deps, SSE)
    graph/               LangGraph nodes: intake, clarify, fanout, compose, verify
    providers/           flights.py stays.py weather.py places.py routing.py
    models/               TripSpec, Trip, Money, Source (Pydantic)
  workers/              arq jobs: plan_trip, refresh_prices, send_alerts
  packages/api-client/  TS client generated from OpenAPI
  infra/                docker-compose.yml, deploy config
  evals/                golden trips + checkers
  docs/                 this file + progress + ADRs
```

This repo has **not** been restructured into this layout yet — it's still
the single-service Python app at the repo root. That's a deliberate,
explicit decision point (see `docs/progress.md`), not an oversight.

## 12. Demo mode & go-live checklist (for public launch, not yet relevant)

Required before any public link: a "try a sample trip" showcase mode with
zero API cost, one live guest plan per visitor/day, hard spend caps on every
provider dashboard, graceful degradation on provider failure. Go-live
checklist: custom domain + HTTPS + OG image, uptime monitor + Sentry
alerts, no cold starts during launch week, no secrets in git history, rate
limits verified from incognito, README with screenshots/demo video, mobile
tested on a real phone.
