import type { ZoneRisk } from "./priority";

// V1 : risque déduit du nom de zone (réglable dans l'éditeur de zones en P2-a.3).
const HIGH = ["fonderie", "coulée", "cariste", "presse"];
const LOW = ["bureau", "mezzanine", "accueil"];

export function riskOf(zone: string | null): ZoneRisk {
  const z = (zone ?? "").toLowerCase();
  if (HIGH.some((k) => z.includes(k))) return "high";
  if (LOW.some((k) => z.includes(k))) return "low";
  return "medium";
}
