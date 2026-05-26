"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { dataApi, type DataSummaryItem } from "@/lib/api";

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"] as const;

interface PresetCategory {
  label: string;
  exchange: string;
  symbols: string[];
}

const PRESET_CATEGORIES: PresetCategory[] = [
  { label: "BIST", exchange: "BIST", symbols: ["XU100", "AKBNK", "THYAO", "GARAN", "ASELS", "SISE"] },
  { label: "US Stocks", exchange: "NASDAQ", symbols: ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN"] },
  { label: "Crypto", exchange: "BINANCE", symbols: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"] },
  { label: "Commodities", exchange: "TVC", symbols: ["UKOIL", "GOLD", "SILVER"] },
  { label: "Forex", exchange: "FX_IDC", symbols: ["EURUSD", "GBPUSD", "USDJPY"] },
];

export default function DataPage() {
  const queryClient = useQueryClient();

  // Single download
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [exchange, setExchange] = useState("BINANCE");
  const [interval, setInterval] = useState("1h");
  const [nBars, setNBars] = useState(1000);

  // Bulk download
  const [selectedSymbols, setSelectedSymbols] = useState<Map<string, string>>(new Map());
  const [bulkTimeframes, setBulkTimeframes] = useState<string[]>(["1d"]);
  const [bulkBars, setBulkBars] = useState(1000);
  const [bulkProgress, setBulkProgress] = useState<{ current: number; total: number; symbol?: string } | null>(null);
  const [summarySymbolFilter, setSummarySymbolFilter] = useState("");
  const [summaryExchangeFilter, setSummaryExchangeFilter] = useState("");
  const [summaryTimeframeFilter, setSummaryTimeframeFilter] = useState("");
  const [summaryMinBarsFilter, setSummaryMinBarsFilter] = useState("");
  const { refetch: refetchSymbols } = useQuery({
    queryKey: ["symbols"],
    queryFn: dataApi.getSymbols,
  });

  const { data: summary } = useQuery({
    queryKey: ["data-summary"],
    queryFn: dataApi.getSummary,
  });

  const downloadMutation = useMutation({
    mutationFn: dataApi.download,
    onSuccess: () => {
      refetchSymbols();
      queryClient.invalidateQueries({ queryKey: ["data-summary"] });
    },
  });

  const toggleSymbol = (sym: string, exc: string) => {
    setSelectedSymbols((prev) => {
      const next = new Map(prev);
      const key = `${exc}:${sym}`;
      if (next.has(key)) next.delete(key);
      else next.set(key, exc);
      return next;
    });
  };

  const toggleCategory = (cat: PresetCategory) => {
    const allSelected = cat.symbols.every((s) => selectedSymbols.has(`${cat.exchange}:${s}`));
    setSelectedSymbols((prev) => {
      const next = new Map(prev);
      cat.symbols.forEach((s) => {
        const key = `${cat.exchange}:${s}`;
        if (allSelected) next.delete(key);
        else next.set(key, cat.exchange);
      });
      return next;
    });
  };

  const toggleTimeframe = (tf: string) => {
    setBulkTimeframes((prev) =>
      prev.includes(tf) ? prev.filter((t) => t !== tf) : [...prev, tf]
    );
  };

  const handleBulkDownload = async () => {
    const entries = Array.from(selectedSymbols.entries());
    const totalOps = entries.length * bulkTimeframes.length;
    let current = 0;

    setBulkProgress({ current: 0, total: totalOps });

    for (const tf of bulkTimeframes) {
      for (const [key] of entries) {
        const [exc, sym] = [key.split(":")[0], key.split(":").slice(1).join(":")];
        current++;
        setBulkProgress({ current, total: totalOps, symbol: sym });

        try {
          await dataApi.download({
            symbol: sym,
            exchange: exc,
            interval: tf,
            n_bars: bulkBars,
          });
        } catch {
          // continue on individual failures
        }
      }
    }

    setBulkProgress(null);
    refetchSymbols();
    queryClient.invalidateQueries({ queryKey: ["data-summary"] });
  };

  const exchangeOptions = useMemo(
    () =>
      Array.from(
        new Set((summary || []).map((item) => item.exchange || "").filter(Boolean))
      ).sort(),
    [summary]
  );
  const timeframeOptions = useMemo(
    () => Array.from(new Set((summary || []).map((item) => item.timeframe))).sort(),
    [summary]
  );
  const filteredSummary = useMemo(() => {
    const minBars = summaryMinBarsFilter === "" ? undefined : Number(summaryMinBarsFilter);
    return (summary || []).filter((item) => {
      if (
        summarySymbolFilter &&
        !item.symbol.toLowerCase().includes(summarySymbolFilter.toLowerCase())
      ) {
        return false;
      }
      if (
        summaryExchangeFilter &&
        (item.exchange || "").toLowerCase() !== summaryExchangeFilter.toLowerCase()
      ) {
        return false;
      }
      if (summaryTimeframeFilter && item.timeframe !== summaryTimeframeFilter) {
        return false;
      }
      if (minBars != null && !Number.isNaN(minBars) && item.bars < minBars) {
        return false;
      }
      return true;
    });
  }, [
    summary,
    summarySymbolFilter,
    summaryExchangeFilter,
    summaryTimeframeFilter,
    summaryMinBarsFilter,
  ]);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Data Manager</h1>

      {/* Single download */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-4 text-lg font-semibold">Download Single Symbol</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
          <label className="space-y-1">
            <span className="text-sm text-[var(--muted)]">Symbol</span>
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm text-[var(--muted)]">Exchange</span>
            <input
              value={exchange}
              onChange={(e) => setExchange(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
            />
          </label>
          <label className="space-y-1">
            <span className="text-sm text-[var(--muted)]">Interval</span>
            <select
              value={interval}
              onChange={(e) => setInterval(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
            >
              {["1m","5m","15m","30m","1h","4h","1d","1w"].map((tf) => (
                <option key={tf} value={tf}>{tf}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-sm text-[var(--muted)]">Bars</span>
            <input
              type="number"
              value={nBars}
              onChange={(e) => setNBars(+e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
            />
          </label>
          <div className="flex items-end">
            <button
              onClick={() => downloadMutation.mutate({ symbol, exchange, interval, n_bars: nBars })}
              disabled={downloadMutation.isPending}
              className="w-full rounded-lg bg-[var(--primary)] px-4 py-2 font-medium text-white disabled:opacity-50"
            >
              {downloadMutation.isPending ? "Downloading..." : "Download"}
            </button>
          </div>
        </div>

        {downloadMutation.data && (
          <div className={`mt-3 rounded-lg p-3 text-sm ${
            downloadMutation.data.success
              ? "bg-green-950/30 text-[var(--success)]"
              : "bg-red-950/30 text-[var(--danger)]"
          }`}>
            {downloadMutation.data.success
              ? `Downloaded ${downloadMutation.data.bars_downloaded} bars for ${downloadMutation.data.symbol}`
              : `Failed: ${downloadMutation.data.error}`}
          </div>
        )}
      </div>

      {/* Bulk download */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-4 text-lg font-semibold">Bulk Download</h2>

        {/* Category presets */}
        <div className="space-y-3 mb-4">
          {PRESET_CATEGORIES.map((cat) => {
            const allSelected = cat.symbols.every((s) =>
              selectedSymbols.has(`${cat.exchange}:${s}`)
            );
            return (
              <div key={cat.label} className="flex items-center gap-2 flex-wrap">
                <button
                  onClick={() => toggleCategory(cat)}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors min-w-[120px] ${
                    allSelected
                      ? "bg-[var(--primary)] text-white"
                      : "border border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {cat.label}
                </button>
                <div className="flex gap-1.5 flex-wrap">
                  {cat.symbols.map((sym) => {
                    const key = `${cat.exchange}:${sym}`;
                    const isSelected = selectedSymbols.has(key);
                    return (
                      <button
                        key={key}
                        onClick={() => toggleSymbol(sym, cat.exchange)}
                        className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
                          isSelected
                            ? "bg-[var(--primary)]/20 text-[var(--primary)] border border-[var(--primary)]/50"
                            : "bg-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
                        }`}
                      >
                        {sym}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Timeframe selection */}
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm text-[var(--muted)]">Timeframes:</span>
          <div className="flex gap-1.5">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => toggleTimeframe(tf)}
                className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
                  bulkTimeframes.includes(tf)
                    ? "bg-[var(--primary)] text-white"
                    : "bg-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-[var(--muted)]">Bars:</span>
            <input
              type="number"
              value={bulkBars}
              onChange={(e) => setBulkBars(+e.target.value)}
              className="w-24 rounded-lg border border-[var(--border)] bg-transparent px-2 py-1.5 text-sm"
              min={100}
              max={10000}
            />
          </label>
        </div>

        {/* Download button */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleBulkDownload}
            disabled={selectedSymbols.size === 0 || bulkTimeframes.length === 0 || !!bulkProgress}
            className="rounded-lg bg-[var(--primary)] px-6 py-2 font-medium text-white disabled:opacity-50"
          >
            {bulkProgress
              ? `Downloading ${bulkProgress.current}/${bulkProgress.total}...`
              : `Download ${selectedSymbols.size} symbols × ${bulkTimeframes.length} timeframes`}
          </button>
          {selectedSymbols.size > 0 && (
            <button
              onClick={() => setSelectedSymbols(new Map())}
              className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
            >
              Clear Selection
            </button>
          )}
        </div>

        {/* Bulk progress */}
        {bulkProgress && (
          <div className="mt-3 space-y-1">
            <div className="flex justify-between text-xs text-[var(--muted)]">
              <span>Downloading {bulkProgress.symbol}...</span>
              <span>{Math.round((bulkProgress.current / bulkProgress.total) * 100)}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
              <div
                className="h-full rounded-full bg-[var(--primary)] transition-all duration-300"
                style={{ width: `${(bulkProgress.current / bulkProgress.total) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Database Info Table */}

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="mb-4 text-lg font-semibold">
          Database Contents
          {summary && <span className="ml-2 text-sm font-normal text-[var(--muted)]">({filteredSummary.length}/{summary.length} entries)</span>}
        </h2>
        <div className="mb-4 grid grid-cols-1 gap-2 md:grid-cols-4">
          <input
            value={summarySymbolFilter}
            onChange={(e) => setSummarySymbolFilter(e.target.value)}
            placeholder="Filter symbol"
            className="rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-xs"
          />
          <select
            value={summaryExchangeFilter}
            onChange={(e) => setSummaryExchangeFilter(e.target.value)}
            className="rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-xs"
          >
            <option value="">All exchanges</option>
            {exchangeOptions.map((exc) => (
              <option key={exc} value={exc}>
                {exc}
              </option>
            ))}
          </select>
          <select
            value={summaryTimeframeFilter}
            onChange={(e) => setSummaryTimeframeFilter(e.target.value)}
            className="rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-xs"
          >
            <option value="">All timeframes</option>
            {timeframeOptions.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={0}
            value={summaryMinBarsFilter}
            onChange={(e) => setSummaryMinBarsFilter(e.target.value)}
            placeholder="Min bars"
            className="rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-xs"
          />
        </div>
        {summary && summary.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
                  <th className="px-3 py-2">Symbol</th>
                  <th className="px-3 py-2">Exchange</th>
                  <th className="px-3 py-2">Timeframe</th>
                  <th className="px-3 py-2 text-right">Bars</th>
                  <th className="px-3 py-2">First Date</th>
                  <th className="px-3 py-2">Last Date</th>
                </tr>
              </thead>
              <tbody>
                {filteredSummary.map((item: DataSummaryItem, i: number) => (
                  <tr key={i} className="border-b border-[var(--border)]/30 hover:bg-[var(--border)]/20">
                    <td className="px-3 py-2 font-medium">{item.symbol}</td>
                    <td className="px-3 py-2 text-[var(--muted)]">{item.exchange || "--"}</td>
                    <td className="px-3 py-2">
                      <span className="rounded bg-[var(--border)] px-1.5 py-0.5 text-xs">{item.timeframe}</span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{item.bars.toLocaleString()}</td>
                    <td className="px-3 py-2 text-xs text-[var(--muted)]">{item.first_date?.slice(0, 10) || "--"}</td>
                    <td className="px-3 py-2 text-xs text-[var(--muted)]">{item.last_date?.slice(0, 10) || "--"}</td>
                  </tr>
                ))}
                {summary.length > 0 && filteredSummary.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-sm text-[var(--muted)]">
                      No entries match current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-[var(--muted)]">No cached data. Download some data to get started.</p>
        )}
      </div>
    </div>
  );
}
