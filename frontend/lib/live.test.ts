import { rosterFromResults, alertFromEvent, formatClock } from "./live";
import type { ComplianceResult, ViolationEvent } from "@/lib/types";

test("formatClock formate en mm:ss", () => {
  expect(formatClock(0)).toBe("00:00");
  expect(formatClock(75.4)).toBe("01:15");
});

test("rosterFromResults ne garde que les personnes suivies", () => {
  const results: ComplianceResult[] = [
    { track_id: 7, zone: "z", required: ["casque"], present: [], missing: ["casque"], compliant: false },
    { track_id: null, zone: null, required: [], present: [], missing: [], compliant: true },
  ];
  const roster = rosterFromResults(results);
  expect(roster).toHaveLength(1);
  expect(roster[0]).toMatchObject({ trackId: 7, compliant: false, missing: ["casque"] });
});

test("alertFromEvent applique le risque de zone à la sévérité", () => {
  const ev: ViolationEvent = { track_id: 37, zone: "Fonderie", missing: ["casque"], timestamp: 12, camera: "cam-1" };
  const alert = alertFromEvent(ev, () => "high");
  expect(alert.severity).toBe("crit");
  expect(alert.personId).toBe("#37");
  expect(alert.time).toBe("00:12");
  expect(alert.zone).toBe("Fonderie");
  expect(alert.missing).toEqual(["casque"]);
  expect(alert.status).toBe("active");
});
