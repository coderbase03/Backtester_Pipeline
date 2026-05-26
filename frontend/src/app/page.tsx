"use client";

import { useQuery } from "@tanstack/react-query";
import { MetricCard } from "@/components/ui/metric-card";
import { strategiesApi, healthApi } from "@/lib/api";

export default function DashboardPage() {
  const { data: strategies } = useQuery({
    queryKey: ["strategies"],
    queryFn: strategiesApi.list,
  });

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: healthApi.check,
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="mt-1 text-[var(--muted)]">
          Opus Backtrader - AI-powered quantitative trading system
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Available Strategies"
          value={String(strategies?.length ?? 0)}
        />
        <MetricCard
          label="Data Source"
          value="TradingView"
        />
        <MetricCard
          label="API Status"
          value={health?.status === "ok" ? "Online" : "Offline"}
          positive={health?.status === "ok"}
          delta={health?.status === "ok" ? "Connected" : "Disconnected"}
        />
        <MetricCard
          label="Markets"
          value="4"
          delta="Stocks, Crypto, Forex, Futures"
        />
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-4 text-xl font-semibold">Available Strategies</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {strategies?.map((s) => (
            <div
              key={s.name}
              className="rounded-lg border border-[var(--border)] p-4 transition-colors hover:border-[var(--primary)]"
            >
              <h3 className="font-medium">{s.class_name}</h3>
              <p className="mt-1 text-sm text-[var(--muted)]">
                {s.description || "No description"}
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                {Object.entries(s.params)
                  .slice(0, 4)
                  .map(([k, v]) => (
                    <span
                      key={k}
                      className="rounded bg-[var(--border)] px-2 py-0.5 text-xs"
                    >
                      {k}={String(v)}
                    </span>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
