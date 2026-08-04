"use client";

export type DashFilters = { zone: string; ppe: string; range: "hour" | "day" | "all" };

const PPE = ["helmet", "safety-vest", "mask", "shoes"];
const RANGES: { v: DashFilters["range"]; l: string }[] = [
  { v: "hour", l: "Dernière heure" },
  { v: "day", l: "Dernier jour" },
  { v: "all", l: "Tout" },
];
const sel = "rounded-lg border border-line bg-s1 px-3 py-1.5 text-[13px] font-semibold text-ink2";

export function DashboardFilters({
  filters, onChange,
}: { filters: DashFilters; onChange: (f: DashFilters) => void }) {
  const set = (patch: Partial<DashFilters>) => onChange({ ...filters, ...patch });
  return (
    <div className="flex items-center gap-2.5">
      <input aria-label="Zone" value={filters.zone} placeholder="Zone…"
             onChange={(e) => set({ zone: e.target.value })}
             className="max-w-[200px] rounded-lg border border-line bg-s1 px-3 py-1.5 text-[13px] text-ink placeholder:text-ink3" />
      <select aria-label="EPI" className={sel} value={filters.ppe}
              onChange={(e) => set({ ppe: e.target.value })}>
        <option value="">Tous EPI</option>
        {PPE.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <select aria-label="Période" className={sel} value={filters.range}
              onChange={(e) => set({ range: e.target.value as DashFilters["range"] })}>
        {RANGES.map((r) => <option key={r.v} value={r.v}>{r.l}</option>)}
      </select>
    </div>
  );
}
