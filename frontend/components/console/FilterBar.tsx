export function FilterBar() {
  return (
    <div className="flex items-center gap-2.5 border-b border-line bg-bg px-4 py-2.5">
      <div className="flex items-center gap-2.5 rounded-lg border border-line2 bg-s2 px-3 py-1.5 font-bold">
        <span className="h-1.5 w-1.5 rounded-full bg-ok" />
        Meknès-Nord
      </div>
      <input
        aria-label="Rechercher"
        className="min-w-0 max-w-[320px] flex-1 rounded-lg border border-line bg-s1 px-3 py-1.5 text-[13px] text-ink placeholder:text-ink3"
        placeholder="Rechercher un ID, une zone…"
      />
      {["Zone", "EPI", "Période", "Statut"].map((f) => (
        <button key={f} className="rounded-lg border border-line bg-s1 px-3 py-1.5 font-semibold text-ink2 hover:text-ink">
          {f}
        </button>
      ))}
    </div>
  );
}
