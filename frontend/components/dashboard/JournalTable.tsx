import { SeverityTag } from "@/components/ui/SeverityTag";
import { PpeChip } from "@/components/ui/PpeChip";
import { severityFor } from "@/lib/priority";
import { riskOf } from "@/lib/zoneRisk";
import { snapshotUrl, type ApiEvent } from "@/lib/eventsApi";

function clock(ts: string): string {
  const d = new Date(ts);
  return isNaN(d.getTime()) ? ts : d.toLocaleTimeString("fr-FR");
}

export function JournalTable({ events }: { events: ApiEvent[] }) {
  if (events.length === 0) {
    return <div className="grid place-items-center py-8 text-[12px] text-ink3">Aucune infraction</div>;
  }
  return (
    <table className="w-full border-collapse text-[12px]">
      <thead>
        <tr className="text-left text-ink3">
          {["Preuve", "Heure", "Zone", "Personne", "EPI manquants", "Sévérité"].map((h) => (
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
          </tr>
        ))}
      </tbody>
    </table>
  );
}
