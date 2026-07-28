import type { Severity } from "@/components/ui/severity";
import type { AlertStatus } from "@/components/ui/StatusBadge";

export type Alert = {
  id: string;
  severity: Severity;
  time: string;
  zone: string;
  personId: string;
  missing: string[];
  status: AlertStatus;
};

// ── Contrat WebSocket P1b ──────────────────────────────
export type Detection = {
  cls: string;
  bbox: [number, number, number, number];
  confidence: number;
  track_id: number | null;
};
export type ComplianceResult = {
  track_id: number | null;
  zone: string | null;
  required: string[];
  present: string[];
  missing: string[];
  compliant: boolean;
};
export type ViolationEvent = {
  track_id: number | null;
  zone: string | null;
  missing: string[];
  timestamp: number;
  camera: string;
};
export type FrameResponse = {
  detections: Detection[];
  results: ComplianceResult[];
  events: ViolationEvent[];
};
export type FrameMessage = { frame: string; timestamp: number };
