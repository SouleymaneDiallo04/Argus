import type { Severity } from "@/components/ui/severity";

export type ZoneRisk = "high" | "medium" | "low";

// Poids par EPI : casque le plus critique, masque le moins.
const PPE_WEIGHT: Record<string, number> = {
  casque: 3, helmet: 3,
  gilet: 2, "safety-vest": 2, shoes: 2,
  masque: 1, mask: 1,
};
const RISK_WEIGHT: Record<ZoneRisk, number> = { high: 3, medium: 2, low: 1 };

export function severityFor(risk: ZoneRisk, missing: string[]): Severity {
  const worstPpe = missing.reduce((m, p) => Math.max(m, PPE_WEIGHT[p] ?? 1), 0);
  const score = RISK_WEIGHT[risk] * worstPpe;
  if (score >= 8) return "crit";
  if (score >= 5) return "high";
  if (score >= 3) return "med";
  return "low";
}
