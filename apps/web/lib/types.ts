// Hand-typed to mirror apps/api/models/*.py. The blueprint's stated
// approach (docs/blueprint.md §07) is a client generated from FastAPI's
// OpenAPI schema — that's the right long-term move, but hand-typing is
// faster to get correct right now with no codegen pipeline set up yet.
// Keep this file as the single place that would get replaced by codegen.

export interface Money {
  amount_minor: number;
  currency: string;
}

export interface Source {
  provider: string;
  fetched_at: string;
  url: string | null;
  deep_link: string | null;
}

export interface TripSpec {
  origin: string | null;
  destination: string | null;
  suggest_destination: boolean;
  date_start: string | null;
  date_end: string | null;
  flexible_dates: boolean;
  travelers: number;
  budget: Money | null;
  pace: "relaxed" | "balanced" | "packed";
  interests: string[];
  constraints: string[];
}

export interface FlightOffer {
  id: string;
  airline: string;
  dep_iata: string;
  arr_iata: string;
  depart_at: string | null;
  arrive_at: string | null;
  duration_minutes: number | null;
  price: Money | null;
  source: Source;
}

export interface StayOffer {
  id: string;
  name: string;
  rating: number | null;
  lat: number | null;
  lng: number | null;
  price_per_night: Money | null;
  source: Source;
}

export interface DayWeather {
  date: string;
  temp_min_c: number | null;
  temp_max_c: number | null;
  condition: string;
  precipitation_mm: number | null;
  is_historical_average: boolean;
}

export interface Slot {
  start: string;
  end: string;
  kind: "activity" | "meal" | "transit" | "stay";
  place_id: string | null;
  title: string;
  lat: number | null;
  lng: number | null;
  cost: Money | null;
  source: Source | null;
  notes: string | null;
}

export interface Day {
  date: string;
  weather: DayWeather | null;
  slots: Slot[];
}

export interface BudgetBreakdown {
  total: Money;
  limit: Money | null;
  by_category: Record<string, Money>;
  fits_budget: boolean | null;
}

export interface Trip {
  id: string;
  spec: TripSpec;
  flights: FlightOffer[];
  stays: StayOffer[];
  days: Day[];
  budget: BudgetBreakdown;
  warnings: string[];
  version: number;
}

export type PlanResponse =
  | { success: true; status: "needs_input"; thread_id: string; question: { field: string; question: string } }
  | { success: true; status: "done"; thread_id: string; trip: Trip }
  | { success: false; error: string };
