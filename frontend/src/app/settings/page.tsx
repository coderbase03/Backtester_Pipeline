"use client";

import { useQuery } from "@tanstack/react-query";
import { healthApi } from "@/lib/api";
import { MetricCard } from "@/components/ui/metric-card";

export default function SettingsPage() {
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: healthApi.check,
    refetchInterval: 10_000,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Settings</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <MetricCard
          label="API Status"
          value={health?.status === "ok" ? "Online" : "Offline"}
          positive={health?.status === "ok"}
        />
        <MetricCard label="Backend" value="FastAPI" delta="localhost:8000" />
        <MetricCard label="Database" value="PostgreSQL" delta="localhost:5432" />
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-4 text-lg font-semibold">API Configuration</h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-[var(--muted)]">API URL</span>
            <code className="text-[var(--foreground)]">
              {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
            </code>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--muted)]">WebSocket URL</span>
            <code className="text-[var(--foreground)]">
              {process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}
            </code>
          </div>
        </div>
      </div>
    </div>
  );
}
