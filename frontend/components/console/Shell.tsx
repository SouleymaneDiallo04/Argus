"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { NavRail } from "./NavRail";
import { useAuth } from "@/components/auth/AuthProvider";

export function Shell({
  active, children,
}: { active: "live" | "analytique"; children: React.ReactNode }) {
  const { user, ready } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (ready && !user) router.push("/login");
  }, [ready, user, router]);
  if (!ready || !user) return null;
  return (
    <div className="grid h-dvh grid-cols-[60px_1fr]">
      <NavRail active={active} />
      <div className="grid min-h-0 min-w-0">{children}</div>
    </div>
  );
}
