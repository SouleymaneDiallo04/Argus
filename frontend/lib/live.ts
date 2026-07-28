import type { Alert, ComplianceResult, ViolationEvent } from "@/lib/types";
import { severityFor, ZoneRisk } from "./priority";

export type RosterEntry = {
  trackId: number;
  zone: string | null;
  missing: string[];
  compliant: boolean;
};

export function formatClock(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function rosterFromResults(results: ComplianceResult[]): RosterEntry[] {
  return results
    .filter((r): r is ComplianceResult & { track_id: number } => r.track_id != null)
    .map((r) => ({ trackId: r.track_id, zone: r.zone, missing: r.missing, compliant: r.compliant }));
}

export function alertFromEvent(ev: ViolationEvent, riskOf: (zone: string | null) => ZoneRisk): Alert {
  return {
    id: `${ev.track_id}-${ev.timestamp}`,
    severity: severityFor(riskOf(ev.zone), ev.missing),
    time: formatClock(ev.timestamp),
    zone: ev.zone ?? "—",
    personId: `#${ev.track_id}`,
    missing: ev.missing,
    status: "active",
  };
}
