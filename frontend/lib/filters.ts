import type { Alert } from "./types";
import type { RosterEntry } from "./live";

export type Filters = { zone?: string; ppe?: string; status?: Alert["status"]; query?: string };

const idMatches = (id: string | number, q?: string) => !q || String(id).includes(q.replace("#", ""));
const zoneMatches = (zone: string | null, z?: string) =>
  !z || (zone ?? "").toLowerCase().includes(z.toLowerCase());

export function filterRoster(roster: RosterEntry[], f: Filters): RosterEntry[] {
  return roster.filter(
    (r) => (!f.ppe || r.missing.includes(f.ppe)) && zoneMatches(r.zone, f.zone) && idMatches(r.trackId, f.query)
  );
}

export function filterAlerts(alerts: Alert[], f: Filters): Alert[] {
  return alerts.filter(
    (a) =>
      (!f.status || a.status === f.status) &&
      (!f.ppe || a.missing.includes(f.ppe)) &&
      zoneMatches(a.zone, f.zone) &&
      idMatches(a.personId, f.query)
  );
}
