"use client";

import { useRouter } from "next/navigation";
import posthog from "posthog-js";
import { useState } from "react";

export function PlanStartForm() {
  const [value, setValue] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const message = value.trim();
    if (!message) return;
    posthog.capture("plan_started", { message_length: message.length });
    router.push(`/plan?message=${encodeURIComponent(message)}`);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-2 shadow-lg shadow-black/[0.03] sm:flex-row sm:p-2"
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Plan a 4-day trip to Goa for 2, under ₹30,000"
        className="flex-1 rounded-xl bg-transparent px-4 py-3 text-foreground placeholder:text-muted focus:outline-none"
      />
      <button
        type="submit"
        className="rounded-xl bg-primary px-6 py-3 font-medium text-primary-foreground shadow-sm transition hover:opacity-90 active:scale-[0.98]"
      >
        Plan my trip &rarr;
      </button>
    </form>
  );
}
