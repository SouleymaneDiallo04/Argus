import { barWidth } from "@/lib/chart";
import type { ZoneStat } from "@/lib/statsApi";

function barColor(rate: number | null): string {
  if (rate === null) return "var(--slate)";
  if (rate >= 0.9) return "var(--ok)";
  if (rate >= 0.7) return "var(--warn)";
  return "var(--crit)";
}

export function ZoneBreakdown({ data }: { data: ZoneStat[] }) {
  if (data.length === 0) {
    return <div className="grid h-[80px] place-items-center text-[12px] text-ink3">Aucune zone</div>;
  }
  return (
    <div className="flex flex-col gap-2">
      {data.map((z) => (
        <div key={z.zone} className="grid grid-cols-[110px_1fr_46px] items-center gap-2 text-[12px]">
          <span className="truncate text-ink2">{z.zone}</span>
          <div className="h-3 rounded bg-s2">
            <div className="h-full rounded"
                 style={{ width: `${barWidth(z.rate, 100)}%`, background: barColor(z.rate) }} />
          </div>
          <span className="text-right font-mono tabnum text-ink2">
            {z.rate === null ? "—" : `${Math.round(z.rate * 100)}%`}
          </span>
        </div>
      ))}
    </div>
  );
}
