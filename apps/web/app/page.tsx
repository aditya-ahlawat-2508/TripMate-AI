import Link from "next/link";

import { PlanStartForm } from "@/components/plan-start-form";
import { getDemoTrips } from "@/lib/api";
import { formatMoney } from "@/lib/format";

export default async function Home() {
  const demoTrips = await getDemoTrips();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <span className="text-lg font-semibold text-primary">TripMate AI</span>
          <span className="text-xs text-muted">budget-true, India-first trip planning</span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-16">
        <section className="text-center">
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            Plan a trip with real prices, real places.
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-muted">
            Every number on screen is sourced — a real fare, a real weather forecast, a real place. No
            invented prices, ever.
          </p>

          <div className="mx-auto mt-8 max-w-lg">
            <PlanStartForm />
          </div>
        </section>

        {demoTrips.length > 0 && (
          <section className="mt-20">
            <h2 className="text-center text-sm font-semibold uppercase tracking-wide text-muted">
              Try a sample trip — zero API cost
            </h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              {demoTrips.map((trip) => (
                <Link
                  key={trip.id}
                  href={`/trip/${trip.id}`}
                  className="rounded-xl border border-border bg-card p-6 transition hover:border-primary"
                >
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-xl font-semibold text-foreground">{trip.spec.destination}</h3>
                    <span className="text-xs text-muted">{trip.days.length} day{trip.days.length === 1 ? "" : "s"}</span>
                  </div>
                  <p className="mt-2 text-sm text-muted">
                    From {trip.spec.origin} · {trip.spec.travelers} traveler{trip.spec.travelers === 1 ? "" : "s"}
                  </p>
                  <p className="mt-4 text-2xl font-semibold tabular-nums text-primary">
                    {formatMoney(trip.budget.total)}
                  </p>
                </Link>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
