"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { backtestApi } from "@/lib/api";
import { EquityChart } from "@/components/charts/equity-chart";
import { formatCurrency, formatPercent, formatNumber } from "@/lib/utils";

type SortKey = "created_at" | "total_return" | "sharpe_ratio" | "max_drawdown_pct" | "win_rate" | "total_trades" | "profit_factor";

export default function HistoryPage() {
  const queryClient = useQueryClient();
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [filterStrategy, setFilterStrategy] = useState("");
  const [filterSymbol, setFilterSymbol] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortAsc, setSortAsc] = useState(false);
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);

  const historyQuery = useQuery({
    queryKey: ["backtest-history", filterStrategy, filterSymbol],
    queryFn: () =>
      backtestApi.getHistory({
        limit: 200,
        strategy: filterStrategy || undefined,
        symbol: filterSymbol || undefined,
      }),
  });

  const detailQuery = useQuery({
    queryKey: ["backtest-detail", selectedRun],
    queryFn: () => backtestApi.getHistoryDetail(selectedRun!),
    enabled: !!selectedRun,
  });

  const deleteMutation = useMutation({
    mutationFn: backtestApi.deleteHistory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtest-history"] });
      setSelectedRun(null);
    },
  });

  const deleteAllMutation = useMutation({
    mutationFn: backtestApi.deleteAllHistory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtest-history"] });
      setConfirmDeleteAll(false);
    },
  });

  const history = historyQuery.data || [];

  const sorted = [...history].sort((a, b) => {
    const av = a[sortKey] ?? 0;
    const bv = b[sortKey] ?? 0;
    if (typeof av === "string" && typeof bv === "string") return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    return sortAsc ? (Number(av) - Number(bv)) : (Number(bv) - Number(av));
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  const detail = detailQuery.data;
  const strategies = [...new Set(history.map((h) => h.strategy_name))];
  if (filterStrategy && !strategies.includes(filterStrategy)) {
    strategies.unshift(filterStrategy);
  }
  const hasActiveFilters = !!(filterStrategy || filterSymbol);

  const SortHeader = ({ label, sortId }: { label: string; sortId: SortKey }) => (
    <th
      className="px-3 py-2.5 cursor-pointer hover:text-[var(--foreground)] select-none"
      onClick={() => handleSort(sortId)}
    >
      {label} {sortKey === sortId ? (sortAsc ? "↑" : "↓") : ""}
    </th>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Backtest History</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {history.length} results in database
          </p>
        </div>
        {history.length > 0 && (
          <div className="flex gap-2">
            {confirmDeleteAll ? (
              <>
                <button
                  onClick={() => deleteAllMutation.mutate()}
                  disabled={deleteAllMutation.isPending}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white"
                >
                  {deleteAllMutation.isPending ? "Deleting..." : "Confirm Delete All"}
                </button>
                <button
                  onClick={() => setConfirmDeleteAll(false)}
                  className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
                >
                  Cancel
                </button>
              </>
            ) : (
              <button
                onClick={() => setConfirmDeleteAll(true)}
                className="rounded-lg border border-red-500/50 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10"
              >
                Delete All
              </button>
            )}
          </div>
        )}
      </div>

      {/* Filters */}
      {!historyQuery.isError && (
        <div className="flex gap-3">
          <select
            value={filterStrategy}
            onChange={(e) => setFilterStrategy(e.target.value)}
            className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
          >
            <option value="">All Strategies</option>
            {strategies.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <input
            value={filterSymbol}
            onChange={(e) => setFilterSymbol(e.target.value)}
            placeholder="Filter by symbol..."
            className="rounded-lg border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
          />
        </div>
      )}

      {historyQuery.isError ? (
        <div className="rounded-xl border border-red-500/50 bg-red-950/30 p-8 text-center">
          <p className="text-lg text-red-300">Failed to load history</p>
          <p className="mt-2 text-sm text-red-200/80">
            {(historyQuery.error as Error).message}
          </p>
        </div>
      ) : history.length === 0 && !historyQuery.isLoading ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-8 text-center">
          <p className="text-lg text-[var(--muted)]">
            {hasActiveFilters ? "No results for current filters." : "No backtest results yet."}
          </p>
          {hasActiveFilters ? (
            <button
              onClick={() => { setFilterStrategy(""); setFilterSymbol(""); }}
              className="mt-3 rounded-lg border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--border)]/30"
            >
              Clear Filters
            </button>
          ) : (
            <p className="mt-2 text-sm text-[var(--muted)]">
              Run a backtest to see results here.
            </p>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Results table */}
          <div className={`overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)] ${selectedRun ? "lg:col-span-2" : "lg:col-span-3"}`}>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
                  <th className="px-3 py-2.5">Strategy</th>
                  <th className="px-3 py-2.5">Symbol</th>
                  <th className="px-3 py-2.5">TF</th>
                  <SortHeader label="Return" sortId="total_return" />
                  <SortHeader label="Sharpe" sortId="sharpe_ratio" />
                  <SortHeader label="Max DD" sortId="max_drawdown_pct" />
                  <SortHeader label="Win Rate" sortId="win_rate" />
                  <SortHeader label="Trades" sortId="total_trades" />
                  <SortHeader label="PF" sortId="profit_factor" />
                  <SortHeader label="Date" sortId="created_at" />
                  <th className="px-3 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {historyQuery.isLoading && (
                  <tr><td colSpan={11} className="py-12 text-center text-[var(--muted)]">Loading...</td></tr>
                )}
                {sorted.map((h) => (
                  <tr
                    key={h.run_id}
                    onClick={() => setSelectedRun(h.run_id === selectedRun ? null : h.run_id)}
                    className={`border-b border-[var(--border)]/30 cursor-pointer transition-colors ${
                      h.run_id === selectedRun ? "bg-[var(--primary)]/10" : "hover:bg-[var(--border)]/20"
                    }`}
                  >
                    <td className="px-3 py-2 font-medium">{h.strategy_name}</td>
                    <td className="px-3 py-2">{h.symbol}</td>
                    <td className="px-3 py-2 text-[var(--muted)]">{h.interval || h.timeframe || "--"}</td>
                    <td className={`px-3 py-2 tabular-nums ${(h.total_return ?? 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}`}>
                      {h.total_return != null ? formatPercent(h.total_return) : "--"}
                    </td>
                    <td className="px-3 py-2 tabular-nums">{h.sharpe_ratio != null ? formatNumber(h.sharpe_ratio) : "--"}</td>
                    <td className="px-3 py-2 tabular-nums text-[var(--danger)]">
                      {(h.max_drawdown_pct ?? h.max_drawdown) != null
                        ? formatPercent(-Math.abs((h.max_drawdown_pct ?? h.max_drawdown) as number))
                        : "--"}
                    </td>
                    <td className="px-3 py-2 tabular-nums">{h.win_rate != null ? formatPercent(h.win_rate, 1) : "--"}</td>
                    <td className="px-3 py-2 tabular-nums">{h.total_trades ?? "--"}</td>
                    <td className="px-3 py-2 tabular-nums">{h.profit_factor != null ? formatNumber(h.profit_factor) : "--"}</td>
                    <td className="px-3 py-2 text-xs text-[var(--muted)]">
                      {h.created_at ? new Date(h.created_at).toLocaleDateString() : "--"}
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(h.run_id); }}
                        className="text-xs text-red-400 hover:text-red-300"
                        title="Delete"
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Detail panel */}
          {selectedRun && detail && (
            <div className="space-y-4 lg:col-span-1">
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h3 className="mb-3 font-semibold">{detail.strategy_name} - {detail.symbol}</h3>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div><span className="text-[var(--muted)]">Return: </span><span className={(detail.total_return ?? 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}>{formatPercent(detail.total_return ?? 0)}</span></div>
                  <div><span className="text-[var(--muted)]">Sharpe: </span>{formatNumber(detail.sharpe_ratio ?? 0)}</div>
                  <div><span className="text-[var(--muted)]">Sortino: </span>{formatNumber(detail.sortino_ratio ?? 0)}</div>
                  <div><span className="text-[var(--muted)]">Max DD: </span><span className="text-[var(--danger)]">{formatPercent(-Math.abs((detail.max_drawdown_pct ?? detail.max_drawdown ?? 0) as number))}</span></div>
                  <div><span className="text-[var(--muted)]">Win Rate: </span>{formatPercent(detail.win_rate ?? 0, 1)}</div>
                  <div><span className="text-[var(--muted)]">Profit Factor: </span>{formatNumber(detail.profit_factor ?? 0)}</div>
                  <div><span className="text-[var(--muted)]">Total Trades: </span>{detail.total_trades ?? 0}</div>
                  <div><span className="text-[var(--muted)]">SQN: </span>{formatNumber(detail.sqn ?? 0)}</div>
                  <div><span className="text-[var(--muted)]">Won/Lost: </span>{detail.won_trades ?? 0}/{detail.lost_trades ?? 0}</div>
                  <div><span className="text-[var(--muted)]">Buy & Hold: </span>{formatPercent(detail.buy_hold_return ?? 0)}</div>
                  <div><span className="text-[var(--muted)]">Initial: </span>{formatCurrency(detail.initial_cash ?? 100000)}</div>
                  <div><span className="text-[var(--muted)]">Final: </span>{formatCurrency(detail.final_value ?? 0)}</div>
                </div>
                {detail.parameters && Object.keys(detail.parameters).length > 0 && (
                  <div className="mt-3 text-xs">
                    <span className="text-[var(--muted)]">Params: </span>
                    {Object.entries(detail.parameters).map(([k, v]) => (
                      <span key={k} className="mr-2 inline-block rounded bg-[var(--border)] px-1.5 py-0.5">
                        {k}={String(v)}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {detail.equity_curve_json && Array.isArray(detail.equity_curve_json) && detail.equity_curve_json.length > 0 && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h3 className="mb-2 text-sm font-semibold">Equity Curve</h3>
                  <EquityChart data={detail.equity_curve_json} />
                </div>
              )}

              {detail.trades && detail.trades.length > 0 && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h3 className="mb-2 text-sm font-semibold">Trades ({detail.trades.length})</h3>
                  <div className="max-h-64 overflow-y-auto text-xs">
                    <table className="w-full">
                      <thead>
                        <tr className="text-left text-[var(--muted)]">
                          <th className="pb-1">#</th>
                          <th className="pb-1">Dir</th>
                          <th className="pb-1">PnL</th>
                          <th className="pb-1">%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.trades.map((t) => (
                          <tr key={t.trade_num} className="border-b border-[var(--border)]/20">
                            <td className="py-0.5">{t.trade_num}</td>
                            <td className={t.direction === "LONG" ? "text-[var(--success)]" : "text-[var(--danger)]"}>{t.direction}</td>
                            <td className={t.pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}>{formatCurrency(t.pnl)}</td>
                            <td className={t.pnl_pct >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}>{formatPercent(t.pnl_pct)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
