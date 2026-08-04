import { reportUrl } from "./reportsApi";

test("reportUrl construit les URLs CSV/PDF avec filtres", () => {
  expect(reportUrl("csv", { zone: "Fonderie", ppe: "helmet" })).toContain("/reports/events.csv?");
  expect(reportUrl("csv", { zone: "Fonderie" })).toContain("zone=Fonderie");
  expect(reportUrl("pdf", { since: "2026-08-04T00:00" })).toContain("/reports/summary.pdf?");
});
