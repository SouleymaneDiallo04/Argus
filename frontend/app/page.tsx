import { Shell } from "@/components/console/Shell";
import { VitalStrip } from "@/components/console/VitalStrip";
import { Workspace } from "@/components/console/Workspace";

export default function Page() {
  return (
    <Shell active="live">
      <div className="grid min-h-0 grid-rows-[auto_1fr]">
        <VitalStrip />
        <Workspace />
      </div>
    </Shell>
  );
}
