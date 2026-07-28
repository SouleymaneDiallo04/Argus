import type { RosterEntry } from "@/lib/live";
import { PpeChip } from "@/components/ui/PpeChip";

export function Roster({ entries }: { entries: RosterEntry[] }) {
  return (
    <div className="flex min-h-0 flex-col rounded-[10px] border border-line bg-s1">
      <div className="flex items-center gap-2.5 border-b border-line px-3.5 py-2.5">
        <h2 className="text-[14px] font-bold">Conformité · en direct</h2>
        <span className="rounded-full bg-s2 px-2 py-0.5 font-mono text-[11px] font-bold text-ink3 tabnum">
          {entries.length} suivis
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-1.5">
        {entries.length === 0 ? (
          <div className="grid place-items-center py-10 text-[13px] text-ink3">Aucune personne détectée</div>
        ) : (
          entries.map((e) => (
            <div key={e.trackId} className="flex items-center gap-3 rounded-md px-2.5 py-2 hover:bg-s2">
              <span className="w-11 flex-none rounded-md border border-line bg-s2 py-1 text-center font-mono text-[13px] font-bold text-ink2 tabnum">
                #{String(e.trackId).padStart(2, "0")}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold">Personne {e.trackId}</div>
                {e.missing.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {e.missing.map((m) => (
                      <PpeChip key={m} label={m} />
                    ))}
                  </div>
                ) : null}
              </div>
              <span
                className={`flex-none rounded-full px-2.5 py-1 text-[11px] font-bold ${
                  e.compliant ? "bg-ok/15 text-ok" : "bg-crit/15 text-crit"
                }`}
              >
                {e.compliant ? "✓ conforme" : `✗ ${e.missing.length}`}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
