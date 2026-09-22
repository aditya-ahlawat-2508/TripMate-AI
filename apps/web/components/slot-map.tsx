import type { Slot } from "@/lib/types";

/**
 * A minimal, dependency-free scatter-plot of the day's slot coordinates —
 * not a real tile-based map. docs/blueprint.md §07 specifies MapLibre GL
 * JS + a tile provider for the real trip workspace map (pins synced with
 * the timeline, route lines); wiring that up needs a tile provider choice
 * and more UI time than this pass had. This keeps the "map panel synced
 * with the timeline" idea real and working without that dependency.
 */
export function SlotMap({ slots }: { slots: Slot[] }) {
  const points = slots
    .map((s, i) => ({ ...s, i }))
    .filter((s): s is Slot & { i: number; lat: number; lng: number } => s.lat != null && s.lng != null);

  if (points.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card p-6 text-center text-sm text-muted">
        No located stops for this day yet.
      </div>
    );
  }

  const lats = points.map((p) => p.lat);
  const lngs = points.map((p) => p.lng);
  const [minLat, maxLat] = [Math.min(...lats), Math.max(...lats)];
  const [minLng, maxLng] = [Math.min(...lngs), Math.max(...lngs)];
  const pad = 0.15;
  const spanLat = Math.max(maxLat - minLat, 0.01);
  const spanLng = Math.max(maxLng - minLng, 0.01);

  const project = (lat: number, lng: number) => {
    const x = ((lng - minLng) / spanLng) * (1 - 2 * pad) + pad;
    const y = 1 - (((lat - minLat) / spanLat) * (1 - 2 * pad) + pad); // flip: north = up
    return { x: x * 100, y: y * 100 };
  };

  const path = points.map((p) => project(p.lat, p.lng)).map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <svg viewBox="0 0 100 100" className="h-48 w-full text-primary">
        <polyline points={path} fill="none" stroke="currentColor" strokeWidth={0.6} strokeDasharray="2 1.5" opacity={0.5} />
        {points.map((p) => {
          const { x, y } = project(p.lat, p.lng);
          return (
            <g key={p.i}>
              <circle cx={x} cy={y} r={2.2} className="fill-primary" />
              <text x={x} y={y - 3} textAnchor="middle" fontSize={3.5} className="fill-foreground">
                {p.i + 1}
              </text>
            </g>
          );
        })}
      </svg>
      <ol className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        {points.map((p) => (
          <li key={p.i}>
            {p.i + 1}. {p.title}
          </li>
        ))}
      </ol>
    </div>
  );
}
