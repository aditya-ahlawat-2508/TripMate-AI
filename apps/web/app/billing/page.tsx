import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { SiteHeader } from "@/components/site-header";
import { UpgradeButton } from "@/components/upgrade-button";
import { formatMoney } from "@/lib/format";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default async function BillingPage() {
  const { userId, getToken } = await auth();
  if (!userId) redirect("/");

  const token = await getToken();
  let status = { plan: "free", status: "none" };
  try {
    const res = await fetch(`${API_URL}/api/billing/status`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: "no-store",
    });
    if (res.ok) status = (await res.json()) as typeof status;
  } catch {
    // API unreachable — page still renders with the free-plan default.
  }

  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main className="mx-auto max-w-xl px-4 py-16">
        <h1 className="text-2xl font-bold text-foreground">Billing</h1>
        <p className="mt-2 text-sm text-muted">
          Current plan: <span className="font-medium text-foreground capitalize">{status.plan}</span>
          {status.status === "active" && " (active)"}
        </p>

        {status.status !== "active" && (
          <div className="mt-8 rounded-xl border border-border bg-card p-6">
            <h2 className="text-lg font-semibold text-foreground">TripMate Pro</h2>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-primary">{formatMoney({ amount_minor: 24900, currency: "INR" })}<span className="text-sm font-normal text-muted">/mo</span></p>
            <ul className="mt-4 space-y-1 text-sm text-muted">
              <li>Unlimited trip plans</li>
              <li>Price-drop alerts</li>
              <li>Offline mode, PDF/calendar export</li>
            </ul>
            <div className="mt-6">
              <UpgradeButton />
            </div>
            <p className="mt-3 text-xs text-muted">
              Test mode — no real charge. Pricing is a starting hypothesis (docs/blueprint.md §03), not
              validated.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
