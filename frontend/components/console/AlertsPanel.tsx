import { AlertRow } from "@/components/ui/AlertRow";
import { SEVERITY_ORDER } from "@/components/ui/severity";
import type { Alert } from "@/lib/types";

export function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  const sorted = [...alerts].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  );
  const crit = alerts.filter((a) => a.severity === "crit").length;
  return (
    <div className="flex min-h-0 flex-col rounded-[10px] border border-line bg-s1">
      <div className="flex items-center gap-2.5 border-b border-line px-3.5 py-2.5">
        <h2 className="text-[14px] font-bold">File d&apos;alertes</h2>
        <span className="rounded-full bg-crit/15 px-2 py-0.5 font-mono text-[11px] font-bold text-crit tabnum">
          {crit} critiques
        </span>
      </div>
      <div className="grid grid-cols-[88px_52px_1fr_46px_96px] gap-2.5 border-b border-line px-3.5 py-1.5 text-[10px] font-bold uppercase tracking-[.1em] text-ink3">
        <div>Sévérité</div>
        <div>Temps</div>
        <div>Localisation · manque</div>
        <div>ID</div>
        <div className="text-right">Statut</div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full">
          <colgroup>
            <col className="w-[88px]" />
            <col className="w-[52px]" />
            <col />
            <col className="w-[46px]" />
            <col className="w-[96px]" />
          </colgroup>
          <tbody>
            {sorted.map((a) => (
              <AlertRow key={a.id} alert={a} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
