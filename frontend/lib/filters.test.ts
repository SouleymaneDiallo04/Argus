import { filterRoster, filterAlerts } from "./filters";
import type { RosterEntry } from "@/lib/live";
import type { Alert } from "@/lib/types";

const roster: RosterEntry[] = [
  { trackId: 37, zone: "Fonderie", missing: ["casque"], compliant: false },
  { trackId: 8, zone: "Bureau", missing: [], compliant: true },
];

test("filterRoster filtre par EPI manquant et par recherche d'ID", () => {
  expect(filterRoster(roster, { ppe: "casque" }).map((r) => r.trackId)).toEqual([37]);
  expect(filterRoster(roster, { query: "#8" }).map((r) => r.trackId)).toEqual([8]);
});

test("filterAlerts filtre par statut et par zone", () => {
  const alerts: Alert[] = [
    { id: "a", severity: "crit", time: "00:01", zone: "Fonderie", personId: "#37", missing: ["casque"], status: "active" },
    { id: "b", severity: "low", time: "00:02", zone: "Bureau", personId: "#8", missing: ["masque"], status: "resolved" },
  ];
  expect(filterAlerts(alerts, { status: "active" }).map((a) => a.id)).toEqual(["a"]);
  expect(filterAlerts(alerts, { zone: "bureau" }).map((a) => a.id)).toEqual(["b"]);
});
