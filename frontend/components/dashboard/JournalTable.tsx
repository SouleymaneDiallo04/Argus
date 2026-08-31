import { SeverityTag } from "@/components/ui/SeverityTag";
import { PpeChip } from "@/components/ui/PpeChip";
import { StatusBadge, type AlertStatus } from "@/components/ui/StatusBadge";
import { severityFor } from "@/lib/priority";
import { riskOf } from "@/lib/zoneRisk";
import { snapshotUrl, type ApiEvent } from "@/lib/eventsApi";

const actionBtn =
  "rounded border border-line2 px-2 py-0.5 text-[11px] font-bold text-ink2 hover:bg-s2";

function clock(ts: string): string {
  const d = new Date(ts);
  return isNaN(d.getTime()) ? ts : d.toLocaleTimeString("fr-FR");
}

export function JournalTable({
  events, onSetStatus,
}: { events: ApiEvent[]; onSetStatus?: (id: number, status: AlertStatus) => void }) {
  if (events.length === 0) {
    return <div className="grid place-items-center py-8 text-[12px] text-ink3">Aucune infraction</div>;
  }
  return (
    <table className="w-full border-collapse text-[12px]">
      <thead>
        <tr className="text-left text-ink3">
          {["Preuve", "Heure", "Zone", "Personne", "EPI manquants", "Sévérité", "Statut"].map((h) => (
            <th key={h} className="px-2 py-1.5 font-semibold">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {events.map((e) => (
          <tr key={e.id} className="border-t border-line">
            <td className="px-2 py-1.5">
              {e.snapshot ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={snapshotUrl(e.id)} alt="preuve floutée"
                     className="h-9 w-14 rounded object-cover" />
              ) : (
                <span className="text-ink3">—</span>
              )}
            </td>
            <td className="px-2 py-1.5 font-mono tabnum text-ink2">{clock(e.ts)}</td>
            <td className="px-2 py-1.5 text-ink">{e.zone ?? "—"}</td>
            <td className="px-2 py-1.5 font-mono tabnum text-ink2">#{e.track_id}</td>
            <td className="px-2 py-1.5">
              <div className="flex flex-wrap gap-1">
                {e.missing.map((m) => <PpeChip key={m} label={m} />)}
              </div>
            </td>
            <td className="px-2 py-1.5">
              <SeverityTag severity={severityFor(riskOf(e.zone), e.missing)} />
            </td>
            <td className="px-2 py-1.5">
              <div className="flex items-center gap-1.5">
                <StatusBadge status={e.status} />
                {onSetStatus && e.status === "active" && (
                  <button onClick={() => onSetStatus(e.id, "ack")} className={actionBtn}>
                    Acquitter
                  </button>
                )}
                {onSetStatus && e.status !== "resolved" && (
                  <button onClick={() => onSetStatus(e.id, "resolved")} className={actionBtn}>
                    Résoudre
                  </button>
                )}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
