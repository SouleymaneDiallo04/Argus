export type AlertStatus = "active" | "ack" | "resolved";

const CFG: Record<AlertStatus, { label: string; cls: string }> = {
  active: { label: "Active", cls: "bg-crit/15 text-crit" },
  ack: { label: "Acquittée", cls: "bg-warn/15 text-warn" },
  resolved: { label: "Résolue", cls: "bg-ok/15 text-ok" },
};

export function StatusBadge({ status }: { status: AlertStatus }) {
  const c = CFG[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10.5px] font-bold ${c.cls}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {c.label}
    </span>
  );
}
