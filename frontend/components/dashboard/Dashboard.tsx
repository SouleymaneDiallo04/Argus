"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getStats, type Stats } from "@/lib/statsApi";
import { getEvents, type ApiEvent } from "@/lib/eventsApi";
import { KpiRow } from "./KpiRow";
import { ConformityTrend } from "@/components/charts/ConformityTrend";
import { ZoneBreakdown } from "@/components/charts/ZoneBreakdown";
import { JournalTable } from "./JournalTable";
import { DashboardFilters, type DashFilters } from "./DashboardFilters";
import { reportUrl } from "@/lib/reportsApi";

const REFRESH_MS = 15000;

function sinceFor(range: DashFilters["range"]): string | undefined {
  if (range === "all") return undefined;
  const ms = range === "hour" ? 3_600_000 : 86_400_000;
  return new Date(Date.now() - ms).toISOString();
}

export function Dashboard({
  loadStats = getStats,
  loadEvents = getEvents,
}: {
  loadStats?: typeof getStats;
  loadEvents?: typeof getEvents;
}) {
  const [filters, setFilters] = useState<DashFilters>({ zone: "", ppe: "", range: "day" });
  const [stats, setStats] = useState<Stats | null>(null);
  const [events, setEvents] = useState<ApiEvent[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const refresh = useCallback(async () => {
    const f = filtersRef.current;
    const since = sinceFor(f.range);
    const zone = f.zone || undefined;
    try {
      const [s, e] = await Promise.all([
        loadStats({ zone, since }),
        loadEvents({ zone, since, ppe: f.ppe || undefined, limit: 100 }),
      ]);
      setStats(s);
      setEvents(e);
      setLastUpdated(new Date());
    } catch {
      /* garde les dernières données */
    }
  }, [loadStats, loadEvents]);

  useEffect(() => { refresh(); }, [refresh, filters]);

  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) refresh(); }, REFRESH_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const h2 = "mb-2 text-[11px] font-bold uppercase tracking-[.12em] text-ink3";
  const card = "rounded-[10px] border border-line bg-s1 p-3";
  const exportParams = {
    zone: filters.zone || undefined,
    ppe: filters.ppe || undefined,
    since: sinceFor(filters.range),
  };
  const exportLink = "rounded-lg border border-line2 px-3 py-1.5 text-[12px] font-bold text-ink hover:bg-s2";

  return (
    <div className="flex min-h-0 flex-col gap-3.5 overflow-y-auto p-3.5">
      <DashboardFilters filters={filters} onChange={setFilters} />
      <KpiRow stats={stats} lastUpdated={lastUpdated} />
      <div className="grid grid-cols-2 gap-3.5">
        <section className={card}>
          <h2 className={h2}>Conformité dans le temps</h2>
          <ConformityTrend data={stats?.over_time ?? []} />
        </section>
        <section className={card}>
          <h2 className={h2}>Conformité par zone</h2>
          <ZoneBreakdown data={stats?.by_zone ?? []} />
        </section>
      </div>
      <section className={card}>
        <div className="mb-2 flex items-center justify-between">
          <h2 className={h2 + " mb-0"}>Journal d&apos;infractions</h2>
          <div className="flex gap-1.5">
            <a href={reportUrl("csv", exportParams)} download className={exportLink}>CSV</a>
            <a href={reportUrl("pdf", exportParams)} download className={exportLink}>PDF</a>
          </div>
        </div>
        <JournalTable events={events} />
      </section>
    </div>
  );
}
