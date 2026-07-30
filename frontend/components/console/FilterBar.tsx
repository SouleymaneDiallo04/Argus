"use client";

import type { Filters } from "@/lib/filters";

const PPE = ["helmet", "safety-vest", "mask", "shoes"];
const STATUS: { v: string; l: string }[] = [
  { v: "", l: "Tous statuts" },
  { v: "active", l: "Actives" },
  { v: "ack", l: "Acquittées" },
  { v: "resolved", l: "Résolues" },
];

export function FilterBar({
  filters,
  onChange,
  onEditZones,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
  onEditZones?: () => void;
}) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  const selCls = "rounded-lg border border-line bg-s1 px-3 py-1.5 text-[13px] font-semibold text-ink2";

  return (
    <div className="flex items-center gap-2.5 border-b border-line bg-bg px-4 py-2.5">
      <div className="flex items-center gap-2.5 rounded-lg border border-line2 bg-s2 px-3 py-1.5 font-bold">
        <span className="h-1.5 w-1.5 rounded-full bg-ok" />
        Meknès-Nord
      </div>
      <input
        aria-label="Rechercher"
        value={filters.query ?? ""}
        onChange={(e) => set({ query: e.target.value || undefined })}
        className="min-w-0 max-w-[300px] flex-1 rounded-lg border border-line bg-s1 px-3 py-1.5 text-[13px] text-ink placeholder:text-ink3"
        placeholder="Rechercher un ID (ex. #37)…"
      />
      <select
        aria-label="EPI"
        className={selCls}
        value={filters.ppe ?? ""}
        onChange={(e) => set({ ppe: e.target.value || undefined })}
      >
        <option value="">Tous EPI</option>
        {PPE.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
      <select
        aria-label="Statut"
        className={selCls}
        value={filters.status ?? ""}
        onChange={(e) => set({ status: (e.target.value || undefined) as Filters["status"] })}
      >
        {STATUS.map((s) => (
          <option key={s.v} value={s.v}>
            {s.l}
          </option>
        ))}
      </select>
      <div className="flex-1" />
      {onEditZones ? (
        <button
          onClick={onEditZones}
          className="rounded-lg border border-line2 px-3 py-1.5 font-bold text-ink hover:bg-s2"
        >
          Éditer les zones
        </button>
      ) : null}
    </div>
  );
}
