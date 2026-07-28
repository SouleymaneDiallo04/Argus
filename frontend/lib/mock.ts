import type { Alert } from "./types";

export const MOCK_ALERTS: Alert[] = [
  { id: "1", severity: "crit", time: "00:12", zone: "Fonderie·Coulée", personId: "#37", missing: ["casque", "shoes"], status: "active" },
  { id: "2", severity: "crit", time: "00:31", zone: "Fonderie·Coulée", personId: "#56", missing: ["casque"], status: "active" },
  { id: "3", severity: "crit", time: "01:48", zone: "Cariste·Allée 4", personId: "#72", missing: ["gilet"], status: "active" },
  { id: "4", severity: "high", time: "00:34", zone: "Cariste·Allée 4", personId: "#98", missing: ["gilet"], status: "ack" },
  { id: "5", severity: "high", time: "02:05", zone: "Ligne 3·Presse", personId: "#12", missing: ["shoes"], status: "active" },
  { id: "6", severity: "med", time: "03:10", zone: "Entrée chantier", personId: "#01", missing: ["shoes"], status: "ack" },
  { id: "7", severity: "med", time: "03:55", zone: "Atelier B·Soudure", personId: "#23", missing: ["masque"], status: "active" },
  { id: "8", severity: "low", time: "05:02", zone: "Bureau·Mezzanine", personId: "#19", missing: ["masque"], status: "active" },
];
