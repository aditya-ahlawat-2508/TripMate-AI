"use client";

import { useAuth } from "@clerk/nextjs";
import Script from "next/script";
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

declare global {
  interface Window {
    Razorpay: new (options: Record<string, unknown>) => { open: () => void };
  }
}

export function UpgradeButton() {
  const { getToken } = useAuth();
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");

  async function handleUpgrade() {
    setStatus("loading");
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/billing/create-order`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      const razorpay = new window.Razorpay({
        key: data.key_id,
        amount: data.amount,
        currency: data.currency,
        order_id: data.order_id,
        name: "TripMate AI",
        description: "TripMate Pro — monthly",
        theme: { color: "#0D9488" },
        handler: () => {
          window.location.reload();
        },
      });
      razorpay.open();
      setStatus("idle");
    } catch {
      setStatus("error");
    }
  }

  return (
    <>
      <Script src="https://checkout.razorpay.com/v1/checkout.js" strategy="lazyOnload" />
      <button
        onClick={handleUpgrade}
        disabled={status === "loading"}
        className="rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
      >
        {status === "loading" ? "Starting checkout…" : "Upgrade to Pro"}
      </button>
      {status === "error" && <p className="mt-2 text-sm text-accent">Couldn&apos;t start checkout — try again.</p>}
    </>
  );
}
