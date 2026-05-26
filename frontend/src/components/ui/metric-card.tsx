"use client";

import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string;
  delta?: string;
  positive?: boolean;
  className?: string;
}

export function MetricCard({ label, value, delta, positive, className }: MetricCardProps) {
  return (
    <div className={cn("rounded-xl border border-[var(--border)] bg-[var(--card)] p-4", className)}>
      <p className="text-xs text-[var(--muted)]">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
      {delta && (
        <p
          className={cn(
            "mt-1 text-sm font-medium",
            positive === undefined
              ? "text-[var(--muted)]"
              : positive
                ? "text-[var(--success)]"
                : "text-[var(--danger)]"
          )}
        >
          {delta}
        </p>
      )}
    </div>
  );
}
