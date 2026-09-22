"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function PlanStartForm() {
  const [value, setValue] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const message = value.trim();
    if (!message) return;
    router.push(`/plan?message=${encodeURIComponent(message)}`);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Plan a 4-day trip to Goa for 2, under ₹30,000"
        className="flex-1 rounded-lg border border-border bg-card px-4 py-3 text-foreground placeholder:text-muted focus:border-primary focus:outline-none"
      />
      <button
        type="submit"
        className="rounded-lg bg-primary px-6 py-3 font-medium text-primary-foreground transition hover:opacity-90"
      >
        Plan my trip
      </button>
    </form>
  );
}
