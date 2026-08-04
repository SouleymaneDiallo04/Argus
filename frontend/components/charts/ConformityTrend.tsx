import { trendSegments } from "@/lib/chart";
import type { Bucket } from "@/lib/statsApi";

const W = 600;
const H = 120;

export function ConformityTrend({ data }: { data: Bucket[] }) {
  if (data.length === 0) {
    return <div className="grid h-[120px] place-items-center text-[12px] text-ink3">Aucune donnée</div>;
  }
  const segs = trendSegments(data.map((d) => d.rate), W, H);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-[120px] w-full"
         role="img" aria-label="Taux de conformité dans le temps">
      <line x1="0" y1={H} x2={W} y2={H} style={{ stroke: "var(--line)" }} />
      {segs.map((seg, i) => (
        <polyline key={i} fill="none" strokeWidth="2" style={{ stroke: "var(--ok)" }}
                  points={seg.map((p) => `${p.x},${p.y}`).join(" ")} />
      ))}
    </svg>
  );
}
