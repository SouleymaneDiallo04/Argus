import { MetricTile } from "@/components/ui/MetricTile";
import type { Stats } from "@/lib/statsApi";

function pct(rate: number | null): string {
  return rate === null ? "—" : `${Math.round(rate * 100)}%`;
}

export function KpiRow({ stats, lastUpdated }: { stats: Stats | null; lastUpdated: Date | null }) {
  const rate = stats ? stats.global.rate : null;
  const tone: "ok" | "warn" | "crit" | "default" =
    rate === null ? "default" : rate >= 0.9 ? "ok" : rate >= 0.7 ? "warn" : "crit";
  return (
    <div className="grid grid-cols-4 gap-2.5">
      <MetricTile label="Conformité globale" value={pct(rate)} tone={tone} />
      <MetricTile label="Infractions" value={String(stats?.violations.total ?? 0)} tone="warn" />
      <MetricTile label="Zones actives" value={String(stats?.by_zone.length ?? 0)} />
      <MetricTile label="Dernière MAJ"
                  value={lastUpdated ? lastUpdated.toLocaleTimeString("fr-FR") : "—"} />
    </div>
  );
}
