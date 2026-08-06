import { API, qs } from "./http";

export function reportUrl(
  kind: "csv" | "pdf",
  params: { zone?: string; ppe?: string; since?: string } = {},
): string {
  const path = kind === "csv" ? "/reports/events.csv" : "/reports/summary.pdf";
  return `${API}${path}${qs(params)}`;
}
