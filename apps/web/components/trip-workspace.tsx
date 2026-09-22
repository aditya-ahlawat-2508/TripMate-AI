"use client";

import Link from "next/link";
import { useState } from "react";

import { SlotMap } from "@/components/slot-map";
import { formatDate, formatMoney, formatTime } from "@/lib/format";
import type { Trip } from "@/lib/types";

const KIND_ICON: Record<string, string> = {
  activity: "\u{1F4CD}", // 📍
  meal: "\u{1F374}", // 🍴
  transit: "✈️", // ✈️
  stay: "\u{1F3E8}", // 🏨
};

export function TripWorkspace({ trip }: { trip: Trip }) {
  const [dayIndex, setDayIndex] = useState(0);
  const day = trip.days[dayIndex];

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <Link href="/" className="text-lg font-semibold text-primary">
            TripMate AI
          </Link>
          <CopyLinkButton />
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="text-2xl font-bold text-foreground">
          {trip.spec.destination} · {trip.spec.travelers} traveler{trip.spec.travelers === 1 ? "" : "s"}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {trip.spec.origin ? `From ${trip.spec.origin}` : null}
          {trip.spec.date_start ? ` · from ${trip.spec.date_start}` : ""}
        </p>

        {trip.warnings.length > 0 && (
          <div className="mt-4 rounded-lg border border-accent/40 bg-accent/10 p-4 text-sm text-foreground">
            <p className="font-medium text-accent">Some data couldn&apos;t be fetched live:</p>
            <ul className="mt-1 list-inside list-disc space-y-0.5">
              {trip.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_320px]">
          <div>
            <div className="flex gap-2 overflow-x-auto pb-2">
              {trip.days.map((d, i) => (
                <button
                  key={d.date}
                  onClick={() => setDayIndex(i)}
                  className={`shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition ${
                    i === dayIndex
                      ? "bg-primary text-primary-foreground"
                      : "bg-card text-foreground hover:bg-border"
                  }`}
                >
                  Day {i + 1}
                </button>
              ))}
            </div>

            {day?.weather && (
              <p className="mt-3 text-sm text-muted">
                {formatDate(day.date)} · {day.weather.condition}, {day.weather.temp_min_c}°–{day.weather.temp_max_c}°C
                {day.weather.is_historical_average ? " (typical for these dates)" : ""}
              </p>
            )}

            <ol className="mt-4 space-y-3">
              {day?.slots.length ? (
                day.slots.map((slot, i) => (
                  <li key={i} className="flex gap-3 rounded-lg border border-border bg-card p-4">
                    <span className="text-xl">{KIND_ICON[slot.kind] || "•"}</span>
                    <div className="flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className="font-medium text-foreground">{slot.title}</p>
                        {slot.cost && (
                          <span className="tabular-nums text-sm font-semibold text-primary">
                            {formatMoney(slot.cost)}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted">
                        {formatTime(slot.start)}–{formatTime(slot.end)}
                        {slot.source && (
                          <>
                            {" · "}
                            <span title={slot.source.provider}>source ✓</span>
                          </>
                        )}
                      </p>
                    </div>
                  </li>
                ))
              ) : (
                <li className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted">
                  No activities planned for this day yet.
                </li>
              )}
            </ol>
          </div>

          <div className="space-y-6">
            <SlotMap slots={day?.slots ?? []} />

            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-baseline justify-between">
                <h2 className="font-semibold text-foreground">Budget</h2>
                <span className="tabular-nums text-sm text-muted">
                  {formatMoney(trip.budget.total)}
                  {trip.budget.limit ? ` / ${formatMoney(trip.budget.limit)}` : ""}
                </span>
              </div>
              {trip.budget.limit && (
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-border">
                  <div
                    className={`h-full ${trip.budget.fits_budget === false ? "bg-accent" : "bg-primary"}`}
                    style={{
                      width: `${Math.min(
                        100,
                        (trip.budget.total.amount_minor / Math.max(trip.budget.limit.amount_minor, 1)) * 100
                      )}%`,
                    }}
                  />
                </div>
              )}
              <ul className="mt-3 space-y-1 text-sm">
                {Object.entries(trip.budget.by_category).map(([category, money]) => (
                  <li key={category} className="flex justify-between text-muted">
                    <span className="capitalize">{category}</span>
                    <span className="tabular-nums">{formatMoney(money)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function CopyLinkButton() {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(window.location.href);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="rounded-lg border border-border px-3 py-1.5 text-sm text-foreground hover:bg-card"
    >
      {copied ? "Copied!" : "Copy this trip"}
    </button>
  );
}
