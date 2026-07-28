export function PpeChip({ label, missing = true }: { label: string; missing?: boolean }) {
  return (
    <span
      className={`rounded px-1.5 py-[3px] font-mono text-[10px] font-semibold ${
        missing ? "bg-crit/15 text-crit" : "bg-ok/15 text-ok"
      }`}
    >
      {label}
    </span>
  );
}
