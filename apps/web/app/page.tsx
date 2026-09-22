export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-50 px-6 text-center font-sans dark:bg-black">
      <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50">
        TripMate AI
      </h1>
      <p className="max-w-md text-zinc-600 dark:text-zinc-400">
        The frontend is scaffolded but not built yet — see{" "}
        <code className="rounded bg-black/[.06] px-1.5 py-0.5 font-mono text-[0.9em] dark:bg-white/[.08]">
          docs/progress.md
        </code>{" "}
        in the repo root for current status.
      </p>
    </div>
  );
}
