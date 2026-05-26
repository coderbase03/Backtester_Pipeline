"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/backtest", label: "Backtest", icon: "🔬" },
  { href: "/discovery", label: "Strategy Discovery", icon: "🔍" },
  { href: "/optimize", label: "Optimize", icon: "🎯" },
  { href: "/data", label: "Data Manager", icon: "📥" },
  { href: "/converter", label: "Pine Convert", icon: "🔄" },
  { href: "/history", label: "History", icon: "📋" },
  { href: "/settings", label: "Settings", icon: "⚙️" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-[var(--border)] bg-[var(--card)]">
      <div className="flex h-14 items-center gap-2 border-b border-[var(--border)] px-4">
        <span className="text-xl">📈</span>
        <h1 className="text-lg font-bold">Opus Backtrader</h1>
      </div>

      <nav className="flex-1 overflow-y-auto p-3">
        <ul className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                    active
                      ? "bg-[var(--primary)] text-white"
                      : "text-[var(--muted)] hover:bg-[var(--border)] hover:text-[var(--foreground)]"
                  )}
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-[var(--border)] p-3 text-xs text-[var(--muted)]">
        Opus Backtrader v2.0
      </div>
    </aside>
  );
}
