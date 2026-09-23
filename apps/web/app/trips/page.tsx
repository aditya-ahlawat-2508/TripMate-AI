import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { SiteHeader } from "@/components/site-header";
import { getMyTrips } from "@/lib/api";
import { formatMoney } from "@/lib/format";

export default async function TripsPage() {
  const { userId, getToken } = await auth();

  if (!userId) redirect("/");

  const token = await getToken();
  const trips = token ? await getMyTrips(token) : [];

  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="text-2xl font-bold text-foreground">My Trips</h1>

        {trips.length === 0 ? (
          <p className="mt-6 rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted">
            No trips yet.{" "}
            <Link href="/" className="text-primary underline">
              Plan one
            </Link>
            .
          </p>
        ) : (
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {trips.map((trip) => (
              <Link
                key={trip.id}
                href={`/trip/${trip.id}`}
                className="rounded-xl border border-border bg-card p-6 transition hover:border-primary"
              >
                <h2 className="text-lg font-semibold text-foreground">{trip.spec.destination || "Untitled trip"}</h2>
                <p className="mt-1 text-sm text-muted">
                  {trip.spec.date_start ? `From ${trip.spec.date_start}` : "Dates flexible"} ·{" "}
                  {trip.days.length} day{trip.days.length === 1 ? "" : "s"}
                </p>
                <p className="mt-3 text-xl font-semibold tabular-nums text-primary">{formatMoney(trip.budget.total)}</p>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
