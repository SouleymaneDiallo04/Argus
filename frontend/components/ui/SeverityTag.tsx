import { Severity, SEVERITY_LABEL } from "./severity";

const CLS: Record<Severity, string> = {
  crit: "bg-crit/15 text-crit",
  high: "bg-warn/15 text-warn",
  med: "bg-brand/15 text-brand",
  low: "bg-slate/15 text-slate",
};

export function SeverityTag({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-[5px] px-1.5 py-1 font-mono text-[10px] font-bold tracking-wide ${CLS[severity]}`}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  );
}
