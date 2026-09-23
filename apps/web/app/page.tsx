import Link from "next/link";

import { PlanStartForm } from "@/components/plan-start-form";
import { SiteHeader } from "@/components/site-header";
import { getDemoTrips } from "@/lib/api";
import { formatMoney } from "@/lib/format";

const FEATURES = [
  { icon: "✈️", title: "Real fares", body: "Live flight prices from Duffel, timestamped, never guessed." },
  { icon: "☀️", title: "Real weather", body: "Per-day forecasts for your actual travel dates, not today's." },
  { icon: "\u{1F4CD}", title: "Real places", body: "Beaches, restaurants, sights sourced from OpenStreetMap." },
];

export default async function Home() {
  const demoTrips = await getDemoTrips();

  return (
    <div className="min-h-screen bg-background">
      <SiteHeader right={<span className="hidden text-xs text-muted sm:inline">budget-true, India-first trip planning</span>} />

      <main>
        <section className="relative overflow-hidden border-b border-border">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 -z-10"
            style={{
              background:
                "radial-gradient(600px circle at 15% 0%, color-mix(in srgb, var(--primary) 14%, transparent), transparent 60%), radial-gradient(500px circle at 90% 10%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 60%)",
            }}
          />
          <div className="mx-auto max-w-5xl px-4 py-20 text-center sm:py-28">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
              Every price on screen is sourced
            </span>

            <h1 className="mx-auto mt-6 max-w-2xl text-4xl font-bold tracking-tight text-foreground sm:text-6xl">
              Plan a trip with <span className="text-primary">real prices</span>, real places.
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-lg text-muted">
              No invented fares. No generic itinerary. A real, editable plan — built from live data,
              in seconds.
            </p>

            <div className="mx-auto mt-10 max-w-lg">
              <PlanStartForm />
            </div>

            <div className="mx-auto mt-16 grid max-w-3xl gap-6 sm:grid-cols-3">
              {FEATURES.map((f) => (
                <div key={f.title} className="rounded-xl border border-border bg-card/60 p-5 text-left backdrop-blur-sm">
                  <div className="text-2xl">{f.icon}</div>
                  <h3 className="mt-2 text-sm font-semibold text-foreground">{f.title}</h3>
                  <p className="mt-1 text-xs text-muted">{f.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {demoTrips.length > 0 && (
          <section className="mx-auto max-w-5xl px-4 py-20">
            <div className="text-center">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-primary">Zero API cost</h2>
              <p className="mt-1 text-2xl font-bold text-foreground">Try a sample trip</p>
            </div>
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              {demoTrips.map((trip) => (
                <Link
                  key={trip.id}
                  href={`/trip/${trip.id}`}
                  className="group relative overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-sm transition hover:-translate-y-0.5 hover:border-primary hover:shadow-md"
                >
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-xl font-semibold text-foreground">{trip.spec.destination}</h3>
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                      {trip.days.length} day{trip.days.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-muted">
                    From {trip.spec.origin} · {trip.spec.travelers} traveler{trip.spec.travelers === 1 ? "" : "s"}
                  </p>
                  <div className="mt-5 flex items-end justify-between">
                    <p className="text-2xl font-semibold tabular-nums text-foreground">
                      {formatMoney(trip.budget.total)}
                    </p>
                    <span className="text-sm font-medium text-primary opacity-0 transition group-hover:opacity-100">
                      View trip &rarr;
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}
      </main>

      <footer className="border-t border-border py-8 text-center text-xs text-muted">
        TripMate AI &mdash; budget-true, India-first trip planning.
      </footer>
    </div>
  );
}
