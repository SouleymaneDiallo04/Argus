import { NavRail } from "@/components/console/NavRail";
import { VitalStrip } from "@/components/console/VitalStrip";
import { Workspace } from "@/components/console/Workspace";

export default function Page() {
  return (
    <div className="grid h-dvh grid-cols-[60px_1fr]">
      <NavRail />
      <div className="grid min-w-0 grid-rows-[auto_1fr]">
        <VitalStrip />
        <Workspace />
      </div>
    </div>
  );
}
