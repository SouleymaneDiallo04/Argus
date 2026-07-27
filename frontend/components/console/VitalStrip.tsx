export function VitalStrip() {
  const tallies: [string, string, string][] = [
    ["Critique", "3", "text-crit"],
    ["Attention", "6", "text-warn"],
    ["Conformes", "41", "text-ok"],
  ];
  return (
    <section className="grid grid-cols-[auto_1fr_auto] items-center gap-6 border-b border-line bg-s1 px-5 py-3.5">
      <div>
        <div className="mb-1.5 text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">
          Conformité · Site Meknès-Nord
        </div>
        <div className="flex items-baseline gap-2.5">
          <span className="font-mono text-[34px] font-bold leading-none tabnum">87.4%</span>
          <span className="font-mono text-[12px] font-bold text-ok tabnum">▲ 2.1</span>
        </div>
      </div>
      <div />
      <div className="flex items-center gap-2.5">
        {tallies.map(([l, v, c]) => (
          <div key={l} className="flex min-w-[74px] flex-col items-end gap-1 rounded-lg border border-line bg-s2 px-3 py-1.5">
            <span className="text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">{l}</span>
            <b className={`font-mono text-[20px] leading-none tabnum ${c}`}>{v}</b>
          </div>
        ))}
      </div>
    </section>
  );
}
