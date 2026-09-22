import type { PlanResponse, Trip } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function startPlan(message: string): Promise<PlanResponse> {
  const res = await fetch(`${API_URL}/api/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  return res.json();
}

export async function resumePlan(threadId: string, answer: string): Promise<PlanResponse> {
  const res = await fetch(`${API_URL}/api/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, resume_answer: answer }),
  });
  return res.json();
}

export async function getTrip(tripId: string): Promise<Trip | null> {
  const res = await fetch(`${API_URL}/api/plan/${tripId}`, { cache: "no-store" });
  if (!res.ok) return null;
  const data = await res.json();
  return data.success ? data.trip : null;
}

export async function getDemoTrips(): Promise<Trip[]> {
  try {
    const res = await fetch(`${API_URL}/api/demo-trips`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    return data.success ? data.trips : [];
  } catch {
    // API unreachable — landing page should still render, just without
    // the sample-trip cards (see app/page.tsx).
    return [];
  }
}
