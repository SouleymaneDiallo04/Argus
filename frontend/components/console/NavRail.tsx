"use client";

import Link from "next/link";
import { Logo } from "@/components/ui/Logo";

type Item = { label: string; href?: string; key?: "live" | "analytique" };

const ITEMS: Item[] = [
  { label: "Live", href: "/", key: "live" },
  { label: "Alertes" },
  { label: "Zones" },
  { label: "Sites" },
  { label: "Analytique", href: "/dashboard", key: "analytique" },
];

export function NavRail({ active }: { active: "live" | "analytique" }) {
  return (
    <nav className="flex w-[60px] flex-col items-center gap-1 border-r border-line bg-[#090B0F] py-3">
      <div className="mb-3 grid h-[34px] w-[34px] place-items-center rounded-lg bg-gradient-to-br from-brand to-[#2560c9] text-white">
        <Logo size={20} color="#fff" />
      </div>
      {ITEMS.map((it) => {
        const isActive = it.key === active;
        const cls = `grid h-10 w-10 place-items-center rounded-[9px] text-[10px] ${
          isActive ? "bg-brand/15 text-brand" : "text-ink3 hover:bg-s2 hover:text-ink"
        }`;
        return it.href ? (
          <Link key={it.label} href={it.href} title={it.label}
                aria-current={isActive ? "page" : undefined} className={cls}>
            {it.label.slice(0, 2)}
          </Link>
        ) : (
          <button key={it.label} title={it.label} className={cls}>{it.label.slice(0, 2)}</button>
        );
      })}
    </nav>
  );
}
