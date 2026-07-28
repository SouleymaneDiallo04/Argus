import { NavRail } from "@/components/console/NavRail";
import { VitalStrip } from "@/components/console/VitalStrip";
import { FilterBar } from "@/components/console/FilterBar";
import { AlertsPanel } from "@/components/console/AlertsPanel";
import { MetricTile } from "@/components/ui/MetricTile";
import { MOCK_ALERTS } from "@/lib/mock";

export default function Page() {
  return (
    <div className="grid h-dvh grid-cols-[60px_1fr]">
      <NavRail />
      <div className="grid min-w-0 grid-rows-[auto_auto_1fr]">
        <VitalStrip />
        <FilterBar />
        <div className="grid min-h-0 grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] gap-3.5 overflow-hidden p-3.5">
          <div className="flex flex-col gap-3.5">
            <div className="grid flex-1 place-items-center rounded-[10px] border border-line2 bg-[#06080d] text-ink3">
              Flux vidéo · (P2-a.2)
            </div>
            <div className="grid grid-cols-4 gap-2.5">
              <MetricTile label="Personnes / site" value="44" delta="+3" />
              <MetricTile label="Critiques actives" value="3" tone="crit" />
              <MetricTile label="Acquit. moy." value="1:12" />
              <MetricTile label="Conformité 24 h" value="91.2%" tone="ok" />
            </div>
          </div>
          <AlertsPanel alerts={MOCK_ALERTS} />
        </div>
      </div>
    </div>
  );
}
