import type { PlanResponse, Trip } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function startPlan(message: string, token: string | null = null): Promise<PlanResponse> {
  const res = await fetch(`${API_URL}/api/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ message }),
  });
  return res.json();
}

export async function resumePlan(threadId: string, answer: string, token: string | null = null): Promise<PlanResponse> {
  const res = await fetch(`${API_URL}/api/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
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

/** Client-side only — needs a Clerk session token, see app/trips/page.tsx. */
export async function getMyTrips(token: string): Promise<Trip[]> {
  const res = await fetch(`${API_URL}/api/trips`, { headers: authHeaders(token), cache: "no-store" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.success ? data.trips : [];
}
