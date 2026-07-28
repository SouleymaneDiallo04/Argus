import type { Alert } from "@/lib/types";
import { SeverityTag } from "./SeverityTag";
import { StatusBadge } from "./StatusBadge";
import { PpeChip } from "./PpeChip";

const SPINE: Record<string, string> = {
  crit: "bg-crit",
  high: "bg-warn",
  med: "bg-brand",
  low: "bg-slate",
};

export function AlertRow({ alert }: { alert: Alert }) {
  return (
    <tr className="group relative border-b border-line hover:bg-s2">
      <td className="relative py-2.5 pl-4 pr-2">
        <span className={`absolute left-0 top-0 h-full w-[3px] ${SPINE[alert.severity]}`} aria-hidden />
        <SeverityTag severity={alert.severity} />
      </td>
      <td className="px-2 font-mono text-[12px] text-ink3 tabnum">{alert.time}</td>
      <td className="px-2">
        <div className="text-[12.5px] font-semibold">{alert.zone}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          {alert.missing.map((m) => (
            <PpeChip key={m} label={m} />
          ))}
        </div>
      </td>
      <td className="px-2 font-mono text-[13px] font-bold text-ink2 tabnum">{alert.personId}</td>
      <td className="py-2.5 pr-4 text-right">
        <StatusBadge status={alert.status} />
      </td>
    </tr>
  );
}
