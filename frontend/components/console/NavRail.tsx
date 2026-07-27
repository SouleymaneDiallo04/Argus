import { Logo } from "@/components/ui/Logo";

export function NavRail() {
  return (
    <nav className="flex w-[60px] flex-col items-center gap-1 border-r border-line bg-[#090B0F] py-3">
      <div className="mb-3 grid h-[34px] w-[34px] place-items-center rounded-lg bg-gradient-to-br from-brand to-[#2560c9] text-white">
        <Logo size={20} color="#fff" />
      </div>
      {["Live", "Alertes", "Zones", "Sites", "Analytique"].map((n, i) => (
        <button
          key={n}
          title={n}
          className={`grid h-10 w-10 place-items-center rounded-[9px] text-[10px] ${
            i === 0 ? "bg-brand/15 text-brand" : "text-ink3 hover:bg-s2 hover:text-ink"
          }`}
        >
          {n.slice(0, 2)}
        </button>
      ))}
    </nav>
  );
}
