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
