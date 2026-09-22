"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { resumePlan, startPlan } from "@/lib/api";

type Step =
  | { kind: "loading" }
  | { kind: "question"; threadId: string; question: string }
  | { kind: "error"; message: string };

export function PlanFlow() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const message = searchParams.get("message") || "";
  const startedRef = useRef(false);

  const [step, setStep] = useState<Step>(message ? { kind: "loading" } : { kind: "error", message: "No trip request given." });
  const [answer, setAnswer] = useState("");
  const [log, setLog] = useState<{ from: "you" | "tripmate"; text: string }[]>(message ? [{ from: "you", text: message }] : []);

  useEffect(() => {
    if (startedRef.current || !message) return;
    startedRef.current = true;
    startPlan(message).then(handleResponse);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [message]);

  function handleResponse(res: Awaited<ReturnType<typeof startPlan>>) {
    if (!res.success) {
      setStep({ kind: "error", message: res.error });
      return;
    }
    if (res.status === "needs_input") {
      setLog((l) => [...l, { from: "tripmate", text: res.question.question }]);
      setStep({ kind: "question", threadId: res.thread_id, question: res.question.question });
      return;
    }
    router.push(`/trip/${res.trip.id}`);
  }

  function submitAnswer(e: React.FormEvent) {
    e.preventDefault();
    if (step.kind !== "question" || !answer.trim()) return;
    const value = answer.trim();
    setLog((l) => [...l, { from: "you", text: value }]);
    setAnswer("");
    setStep({ kind: "loading" });
    resumePlan(step.threadId, value).then(handleResponse);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3">
        {log.map((entry, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-lg px-4 py-2 text-sm ${
              entry.from === "you"
                ? "self-end bg-primary text-primary-foreground"
                : "self-start bg-card text-foreground"
            }`}
          >
            {entry.text}
          </div>
        ))}
      </div>

      {step.kind === "loading" && (
        <div className="flex items-center gap-2 text-sm text-muted">
          <span className="h-2 w-2 animate-pulse rounded-full bg-primary" />
          Finding flights, stays, weather, and places…
        </div>
      )}

      {step.kind === "error" && (
        <p className="rounded-lg border border-border bg-card p-4 text-sm text-foreground">{step.message}</p>
      )}

      {step.kind === "question" && (
        <form onSubmit={submitAnswer} className="flex gap-2">
          <input
            autoFocus
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            className="flex-1 rounded-lg border border-border bg-card px-4 py-2 text-foreground focus:border-primary focus:outline-none"
          />
          <button
            type="submit"
            className="rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground transition hover:opacity-90"
          >
            Send
          </button>
        </form>
      )}
    </div>
  );
}
