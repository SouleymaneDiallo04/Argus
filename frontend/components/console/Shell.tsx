import type { ReactNode } from "react";
import { NavRail } from "./NavRail";

export function Shell({
  active, children,
}: { active: "live" | "analytique"; children: ReactNode }) {
  return (
    <div className="grid h-dvh grid-cols-[60px_1fr]">
      <NavRail active={active} />
      <div className="grid min-h-0 min-w-0">{children}</div>
    </div>
  );
}
