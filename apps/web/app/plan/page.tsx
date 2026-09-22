import { Suspense } from "react";

import { PlanFlow } from "@/components/plan-flow";

export default function PlanPage() {
  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-4 py-16">
      <Suspense fallback={<p className="text-center text-muted">Loading…</p>}>
        <PlanFlow />
      </Suspense>
    </div>
  );
}
