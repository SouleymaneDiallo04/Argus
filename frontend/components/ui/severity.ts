export type Severity = "crit" | "high" | "med" | "low";

export const SEVERITY_LABEL: Record<Severity, string> = {
  crit: "CRITIQUE",
  high: "ÉLEVÉ",
  med: "MOYEN",
  low: "FAIBLE",
};

export const SEVERITY_ORDER: Severity[] = ["crit", "high", "med", "low"];
