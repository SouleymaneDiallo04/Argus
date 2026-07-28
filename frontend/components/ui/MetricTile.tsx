const TONE: Record<string, string> = {
  crit: "text-crit",
  ok: "text-ok",
  warn: "text-warn",
  default: "text-ink",
};

export function MetricTile({
  label,
  value,
  delta,
  tone = "default",
}: {
  label: string;
  value: string;
  delta?: string;
  tone?: keyof typeof TONE;
}) {
  return (
    <div className="rounded-[9px] border border-line bg-s1 px-3 py-2.5">
      <div className="mb-1.5 text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">{label}</div>
      <b className={`font-mono text-[21px] leading-none tabnum ${TONE[tone] ?? TONE.default}`}>{value}</b>
      {delta ? <span className="ml-1.5 font-mono text-[11px] text-ink2 tabnum">{delta}</span> : null}
    </div>
  );
}
