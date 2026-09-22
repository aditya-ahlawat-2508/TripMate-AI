import type { Money } from "./types";

export function formatMoney(money: Money | null): string {
  if (!money) return "—";
  const amount = money.amount_minor / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: money.currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatTime(value: string): string {
  // Slot.start/end come back as "HH:MM:SS"
  return value.slice(0, 5);
}

export function formatDate(value: string): string {
  return new Date(value + "T00:00:00").toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}
