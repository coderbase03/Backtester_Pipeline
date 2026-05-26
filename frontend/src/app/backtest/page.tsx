"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { strategiesApi, backtestApi, dataApi, type BacktestResult } from "@/lib/api";
import { MetricCard } from "@/components/ui/metric-card";
import { EquityChart } from "@/components/charts/equity-chart";
import { formatCurrency, formatPercent, formatNumber } from "@/lib/utils";

const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"];
const EXCHANGES = ["BINANCE", "NASDAQ", "NYSE", "BIST", "FX_IDC"];
const FALLBACK_SYMBOLS: Record<string, string[]> = {
  BINANCE: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"],
  NASDAQ: ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA"],
  NYSE: ["JPM", "XOM", "JNJ", "KO", "WMT"],
  BIST: ["XU100", "AKBNK", "THYAO", "GARAN", "ASELS"],
  FX_IDC: ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "USDCAD"],
};

interface StrategyParam {
  name: string;
  default: number;
  param_type: string;
}

export default function BacktestPage() {
  const [mode, setMode] = useState<"single" | "multi">("single");

  const [form, setForm] = useState({
    strategy: "supertrend",
    symbol: "BTCUSDT",
    exchange: "BINANCE",
    source: "tradingview",
    interval: "1h",
    n_bars: 1000,
    initial_cash: 100000,
    commission: 0.0005,
    slippage_ticks: 2,
  });

  // Risk management
  const [riskParams, setRiskParams] = useState({
    tp_pct: 3.0,
    sl_pct: 1.5,
    trail_pct: 0.0,
    use_bracket: true,
    trade_direction: "both",
    leverage: 1,
  });

  // Strategy-specific params
  const [strategyParams, setStrategyParams] = useState<Record<string, number>>({});
  const [strategyParamDefs, setStrategyParamDefs] = useState<StrategyParam[]>([]);

  // Multi-symbol
  const [multiSymbols, setMultiSymbols] = useState<string[]>(["BTCUSDT", "ETHUSDT", "AAPL"]);
  const [multiInput, setMultiInput] = useState("");
  const [multiTimeframes, setMultiTimeframes] = useState<string[]>(["1h", "4h", "1d"]);
  const [selectedMultiIndex, setSelectedMultiIndex] = useState<number | null>(null);
  const [showRiskPanel, setShowRiskPanel] = useState(true);
  const [analysisResult, setAnalysisResult] = useState<Awaited<ReturnType<typeof backtestApi.analyzeMultiMatrix>> | null>(null);
  const { data: strategies } = useQuery({
    queryKey: ["strategies"],
    queryFn: strategiesApi.list,
  });
  const { data: cachedSymbols } = useQuery({
    queryKey: ["cached-symbols"],
    queryFn: dataApi.getSymbols,
  });
  const exchangeSymbols = (() => {
    const fromDb = (cachedSymbols || [])
      .filter((s) => (s.exchange || "").toUpperCase() === form.exchange.toUpperCase())
      .map((s) => s.symbol.toUpperCase());
    const merged = [...new Set([...fromDb, ...(FALLBACK_SYMBOLS[form.exchange] || [])])];
    return merged.length ? merged : (FALLBACK_SYMBOLS.BINANCE || []);
  })();

  // Fetch strategy-specific params when strategy changes
  useEffect(() => {
    if (!form.strategy) return;
    strategiesApi.getParams(form.strategy).then((data) => {
      if (data?.params) {
        setStrategyParamDefs(data.params);
        const defaults: Record<string, number> = {};
        data.params.forEach((p: StrategyParam) => {
          if (!["risk_pct", "use_bracket", "tp_pct", "sl_pct", "trail_pct", "trade_direction", "leverage", "log_trades", "position_mode", "fixed_units", "fixed_notional", "cash_buffer_pct"].includes(p.name)) {
            defaults[p.name] = p.default;
          }
        });
        setStrategyParams(defaults);
      }
    }).catch(() => {
      setStrategyParamDefs([]);
      setStrategyParams({});
    });
  }, [form.strategy]);

  useEffect(() => {
    if (!exchangeSymbols.includes(form.symbol)) {
      setForm((prev) => ({ ...prev, symbol: exchangeSymbols[0] || prev.symbol }));
    }
  }, [form.exchange, form.symbol, exchangeSymbols]);

  const buildStrategyParams = () => {
    const params: Record<string, number | boolean | string> = {
      ...strategyParams,
      tp_pct: riskParams.tp_pct,
      sl_pct: riskParams.sl_pct,
      trail_pct: riskParams.trail_pct,
      use_bracket: riskParams.use_bracket,
      trade_direction: riskParams.trade_direction,
      leverage: riskParams.leverage,
    };
    return params;
  };

  const singleMutation = useMutation({
    mutationFn: backtestApi.run,
  });

  const multiMutation = useMutation({
    mutationFn: backtestApi.runMulti,
  });
  const analyzeMutation = useMutation({
    mutationFn: backtestApi.analyzeMultiMatrix,
  });

  const handleSingleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    singleMutation.mutate({
      ...form,
      n_bars: Math.max(1000, form.n_bars),
      strategy_params: buildStrategyParams() as Record<string, number | boolean | string>,
    });
  };

  const handleMultiSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (multiSymbols.length === 0) return;
    setSelectedMultiIndex(null);
      multiMutation.mutate({
      strategy: form.strategy,
      symbols: multiSymbols,
      source: form.source,
      exchange: form.exchange,
      intervals: multiTimeframes,
      n_bars: Math.max(1000, form.n_bars),
      initial_cash: form.initial_cash,
      commission: form.commission,
      slippage_ticks: form.slippage_ticks,
      strategy_params: buildStrategyParams() as Record<string, number | boolean | string>,
    });
  };

  const handleAnalyzeSubmit = () => {
    if (multiSymbols.length === 0 || multiTimeframes.length === 0) return;
    analyzeMutation.mutate(
      {
        strategy: form.strategy,
        symbols: multiSymbols,
        source: form.source,
        exchange: form.exchange,
        intervals: multiTimeframes,
        n_bars: Math.max(1000, form.n_bars),
        initial_cash: form.initial_cash,
        commission: form.commission,
        slippage_ticks: form.slippage_ticks,
        strategy_params: buildStrategyParams() as Record<string, number | boolean | string>,
      },
      { onSuccess: (res) => setAnalysisResult(res) }
    );
  };

  const addMultiSymbol = () => {
    const sym = multiInput.trim().toUpperCase();
    if (sym && !multiSymbols.includes(sym)) {
      setMultiSymbols([...multiSymbols, sym]);
    }
    setMultiInput("");
  };

  const singleResult: BacktestResult | undefined = singleMutation.data;
  const multiResults = multiMutation.data?.results;
  const selectedMultiResult =
    multiResults && selectedMultiIndex !== null ? multiResults[selectedMultiIndex] : undefined;

  useEffect(() => {
    if (!multiResults || multiResults.length === 0) {
      setSelectedMultiIndex(null);
      return;
    }
    if (selectedMultiIndex === null || selectedMultiIndex >= multiResults.length) {
      setSelectedMultiIndex(0);
    }
  }, [multiResults, selectedMultiIndex]);

  const visibleStrategyParams = strategyParamDefs.filter(
    (p) => !["risk_pct", "use_bracket", "tp_pct", "sl_pct", "trail_pct", "trade_direction", "leverage", "log_trades", "position_mode", "fixed_units", "fixed_notional", "cash_buffer_pct"].includes(p.name)
  );

  const singleUnitPnl =
    singleResult?.trades?.reduce((acc, t) => acc + (Number(t.pnl) || 0), 0) ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Backtest</h1>
        <div className="flex gap-1 rounded-lg border border-[var(--border)] p-0.5">
          <button
            onClick={() => setMode("single")}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              mode === "single" ? "bg-[var(--primary)] text-white" : "text-[var(--muted)]"
            }`}
          >
            Single
          </button>
          <button
            onClick={() => setMode("multi")}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              mode === "multi" ? "bg-[var(--primary)] text-white" : "text-[var(--muted)]"
            }`}
          >
            Multi
          </button>
        </div>
      </div>

      {/* Main form */}
      <form onSubmit={mode === "single" ? handleSingleSubmit : handleMultiSubmit}>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 space-y-4">
          {/* Basic params */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <label className="space-y-1">
              <span className="text-sm text-[var(--muted)]">Strategy</span>
              <select
                value={form.strategy}
                onChange={(e) => setForm({ ...form, strategy: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
              >
                {strategies?.map((s) => (
                  <option key={s.name} value={s.name}>{s.class_name}</option>
                ))}
              </select>
            </label>

            <label className="space-y-1">
              <span className="text-sm text-[var(--muted)]">Exchange</span>
              <select
                value={form.exchange}
                onChange={(e) => setForm({ ...form, exchange: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
              >
                {EXCHANGES.map((ex) => <option key={ex} value={ex}>{ex}</option>)}
              </select>
            </label>

            {mode === "single" && (
              <>
                <label className="space-y-1">
                  <span className="text-sm text-[var(--muted)]">Symbol</span>
                  <select
                    value={form.symbol}
                    onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
                  >
                    {exchangeSymbols.map((sym) => <option key={sym} value={sym}>{sym}</option>)}
                  </select>
                </label>
                <label className="space-y-1">
                  <span className="text-sm text-[var(--muted)]">Timeframe</span>
                  <select
                    value={form.interval}
                    onChange={(e) => setForm({ ...form, interval: e.target.value })}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
                  >
                    {TIMEFRAMES.map((tf) => <option key={tf} value={tf}>{tf}</option>)}
                  </select>
                </label>
              </>
            )}

            <label className="space-y-1">
              <span className="text-sm text-[var(--muted)]">Bars</span>
              <input
                type="number"
                value={form.n_bars}
                min={1000}
                onChange={(e) => setForm({ ...form, n_bars: Math.max(1000, +e.target.value) })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
              />
            </label>

            <label className="space-y-1">
              <span className="text-sm text-[var(--muted)]">Initial Cash</span>
              <input
                type="number"
                value={form.initial_cash}
                onChange={(e) => setForm({ ...form, initial_cash: +e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm text-[var(--muted)]">Commission</span>
              <input
                type="number"
                step="0.0001"
                value={form.commission}
                onChange={(e) => setForm({ ...form, commission: +e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
              />
            </label>
            <label className="space-y-1">
              <span className="text-sm text-[var(--muted)]">Slippage (ticks)</span>
              <input
                type="number"
                min={0}
                value={form.slippage_ticks}
                onChange={(e) => setForm({ ...form, slippage_ticks: +e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
              />
            </label>

            <label className="space-y-1">
              <span className="text-sm text-[var(--muted)]">Leverage</span>
              <input
                type="number"
                min={1}
                value={riskParams.leverage}
                onChange={(e) => setRiskParams({ ...riskParams, leverage: +e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
              />
            </label>

            <label className="space-y-1">
              <span className="text-sm text-[var(--muted)]">Direction</span>
              <select
                value={riskParams.trade_direction}
                onChange={(e) => setRiskParams({ ...riskParams, trade_direction: e.target.value })}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
              >
                <option value="both">Both</option>
                <option value="long">Long Only</option>
                <option value="short">Short Only</option>
              </select>
            </label>
          </div>

          {/* Multi-symbol inputs */}
          {mode === "multi" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <input
                  value={multiInput}
                  onChange={(e) => setMultiInput(e.target.value.toUpperCase())}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addMultiSymbol(); } }}
                  placeholder={`Add symbol (${form.exchange})`}
                  className="flex-1 rounded-lg border border-[var(--border)] bg-transparent px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  onClick={addMultiSymbol}
                  className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--border)]"
                >
                  Add
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {exchangeSymbols.slice(0, 12).map((sym) => (
                  <button
                    key={`suggest-${sym}`}
                    type="button"
                    onClick={() => {
                      if (!multiSymbols.includes(sym)) setMultiSymbols([...multiSymbols, sym]);
                    }}
                    className="rounded-md bg-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--primary)] hover:text-white"
                  >
                    + {sym}
                  </button>
                ))}
              </div>
              {multiSymbols.length > 0 && (
                <div className="flex gap-1.5 flex-wrap">
                  {multiSymbols.map((s) => (
                    <span key={s} className="flex items-center gap-1 rounded-lg bg-[var(--border)] px-2.5 py-1 text-sm">
                      {s}
                      <button
                        type="button"
                        onClick={() => setMultiSymbols(multiSymbols.filter((x) => x !== s))}
                        className="text-[var(--muted)] hover:text-[var(--danger)]"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-2">
                <span className="text-sm text-[var(--muted)]">Timeframes:</span>
                {TIMEFRAMES.map((tf) => (
                  <button
                    key={tf}
                    type="button"
                    onClick={() =>
                      setMultiTimeframes((prev) =>
                        prev.includes(tf) ? prev.filter((t) => t !== tf) : [...prev, tf]
                      )
                    }
                    className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
                      multiTimeframes.includes(tf)
                        ? "bg-[var(--primary)] text-white"
                        : "bg-[var(--border)] text-[var(--muted)]"
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Risk management toggle */}
          <button
            type="button"
            onClick={() => setShowRiskPanel(!showRiskPanel)}
            className="flex items-center gap-2 text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
          >
            <span>{showRiskPanel ? "▼" : "▶"}</span>
            Risk Management & Strategy Parameters
          </button>

          {/* Risk management panel */}
          {showRiskPanel && (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4 rounded-lg border border-[var(--border)] p-4 bg-[var(--background)]">
              <label className="space-y-1">
                <span className="text-xs text-[var(--muted)]">Take Profit %</span>
                <input
                  type="number"
                  step="0.1"
                  value={riskParams.tp_pct}
                  onChange={(e) => setRiskParams({ ...riskParams, tp_pct: +e.target.value })}
                  className="w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--muted)]">Stop Loss %</span>
                <input
                  type="number"
                  step="0.1"
                  value={riskParams.sl_pct}
                  onChange={(e) => setRiskParams({ ...riskParams, sl_pct: +e.target.value })}
                  className="w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--muted)]">Trailing Stop %</span>
                <input
                  type="number"
                  step="0.1"
                  value={riskParams.trail_pct}
                  onChange={(e) => setRiskParams({ ...riskParams, trail_pct: +e.target.value })}
                  className="w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                />
              </label>
              <label className="flex items-center gap-2 self-end py-1.5">
                <input
                  type="checkbox"
                  checked={riskParams.use_bracket}
                  onChange={(e) => setRiskParams({ ...riskParams, use_bracket: e.target.checked })}
                  className="rounded"
                />
                <span className="text-xs text-[var(--muted)]">Enable TP/SL/TSL (Bracket)</span>
              </label>

              {/* Strategy-specific params */}
              {visibleStrategyParams.length > 0 && (
                <div className="col-span-full border-t border-[var(--border)] pt-3 mt-1">
                  <span className="text-xs text-[var(--muted)] font-medium mb-2 block">Strategy Parameters</span>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    {visibleStrategyParams.map((p) => (
                      <label key={p.name} className="space-y-1">
                        <span className="text-xs text-[var(--muted)]">{p.name}</span>
                        <input
                          type="number"
                          step="any"
                          value={strategyParams[p.name] ?? p.default}
                          onChange={(e) => setStrategyParams({ ...strategyParams, [p.name]: +e.target.value })}
                          className="w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
                        />
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={singleMutation.isPending || multiMutation.isPending}
            className="w-full rounded-lg bg-[var(--primary)] px-6 py-2.5 font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {(singleMutation.isPending || multiMutation.isPending)
              ? "Running..."
              : mode === "single"
                ? "Run Backtest"
                : `Run ${multiSymbols.length} × ${multiTimeframes.length} Backtests`}
          </button>
          {mode === "multi" && (
            <button
              type="button"
              onClick={handleAnalyzeSubmit}
              disabled={analyzeMutation.isPending || multiSymbols.length === 0 || multiTimeframes.length === 0}
              className="mt-2 w-full rounded-lg border border-[var(--primary)] px-6 py-2.5 font-medium text-[var(--primary)] transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {analyzeMutation.isPending ? "Analyzing..." : "Analyze Matrix"}
            </button>
          )}
        </div>
      </form>

      {/* Error */}
      {(singleMutation.isError || multiMutation.isError) && (
        <div className="rounded-lg border border-[var(--danger)] bg-red-950/30 p-4 text-[var(--danger)]">
          {(singleMutation.error || multiMutation.error)?.message}
        </div>
      )}

      {/* Single result */}
      {mode === "single" && singleResult && (
        <div className="space-y-6">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-xs text-[var(--muted)]">
            Sizing: <span className="text-[var(--foreground)] font-medium">Full Cash @ 1x</span>
            <span> | Initial Cash: <span className="text-[var(--foreground)] font-medium">{formatCurrency(form.initial_cash)}</span></span>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
            <MetricCard label="Total Return" value={formatPercent(singleResult.total_return)} positive={singleResult.total_return >= 0} />
            <MetricCard label="Sharpe Ratio" value={formatNumber(singleResult.sharpe_ratio)} />
            <MetricCard label="Max Drawdown" value={formatPercent(-Math.abs(singleResult.max_drawdown_pct))} positive={false} />
            <MetricCard label="Win Rate" value={formatPercent(singleResult.win_rate, 1)} />
            <MetricCard label="Profit Factor" value={formatNumber(singleResult.profit_factor)} />
            <MetricCard label="Trades" value={String(singleResult.total_trades)} />
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <MetricCard label="Unit PnL (Net)" value={formatCurrency(singleUnitPnl)} positive={singleUnitPnl >= 0} />
            <MetricCard
              label="Avg Trade PnL"
              value={formatCurrency(singleResult.total_trades > 0 ? singleUnitPnl / singleResult.total_trades : 0)}
              positive={(singleResult.total_trades > 0 ? singleUnitPnl / singleResult.total_trades : 0) >= 0}
            />
            <MetricCard label="Final Value" value={formatCurrency(singleResult.final_value)} positive={singleResult.final_value >= singleResult.initial_cash} />
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="mb-3 font-semibold">Equity Curve</h3>
            <EquityChart data={singleResult.equity_curve} />
          </div>

          {singleResult.trades.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="mb-3 font-semibold">Trade History ({singleResult.trades.length})</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-left text-[var(--muted)]">
                      <th className="pb-2">#</th>
                      <th className="pb-2">Direction</th>
                      <th className="pb-2">Entry</th>
                      <th className="pb-2">Exit</th>
                      <th className="pb-2">PnL</th>
                      <th className="pb-2">PnL %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {singleResult.trades.map((t) => (
                      <tr key={t.trade_num} className="border-b border-[var(--border)]/50">
                        <td className="py-1.5">{t.trade_num}</td>
                        <td className={t.direction === "LONG" ? "text-[var(--success)]" : "text-[var(--danger)]"}>{t.direction}</td>
                        <td>{formatCurrency(t.entry_price)}</td>
                        <td>{formatCurrency(t.exit_price)}</td>
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

      {/* Multi results */}
      {mode === "multi" && analysisResult && (
        <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-lg font-semibold">Matrix Analysis</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard label="Total" value={String(analysisResult.summary.total)} />
            <MetricCard label="Success" value={String(analysisResult.summary.success)} />
            <MetricCard label="Failed" value={String(analysisResult.summary.failed)} positive={analysisResult.summary.failed === 0} />
            <MetricCard label="Avg Sharpe" value={formatNumber(analysisResult.summary.avg_sharpe)} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-[var(--muted)]">
                  <th className="py-2">Symbol</th><th>TF</th><th>Return</th><th>Sharpe</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {analysisResult.rows.map((r, i) => (
                  <tr key={`${r.symbol}-${r.interval}-${i}`} className="border-b border-[var(--border)]/30">
                    <td className="py-1.5">{r.symbol}</td>
                    <td>{r.interval}</td>
                    <td>{formatPercent(r.total_return)}</td>
                    <td>{formatNumber(r.sharpe)}</td>
                    <td>{r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {mode === "multi" && multiResults && multiResults.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Results ({multiResults.length} backtests)</h2>
          <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
                  <th className="px-3 py-2.5">Symbol</th>
                  <th className="px-3 py-2.5">TF</th>
                  <th className="px-3 py-2.5">Return</th>
                  <th className="px-3 py-2.5">Sharpe</th>
                  <th className="px-3 py-2.5">Max DD</th>
                  <th className="px-3 py-2.5">Win Rate</th>
                  <th className="px-3 py-2.5">PF</th>
                  <th className="px-3 py-2.5">Trades</th>
                  <th className="px-3 py-2.5">Unit PnL</th>
                  <th className="px-3 py-2.5">Final Value</th>
                  <th className="px-3 py-2.5">Status</th>
                  <th className="px-3 py-2.5 text-right">Detail</th>
                </tr>
              </thead>
              <tbody>
                {multiResults.map((r, i) => (
                  <tr
                    key={i}
                    onClick={() => setSelectedMultiIndex(i)}
                    className={`border-b border-[var(--border)]/30 transition-colors ${
                      i === selectedMultiIndex
                        ? "bg-[var(--primary)]/10"
                        : "hover:bg-[var(--border)]/20"
                    }`}
                  >
                    <td className="px-3 py-2 font-medium">{r.symbol}</td>
                    <td className="px-3 py-2">{r.interval}</td>
                    <td className={`px-3 py-2 tabular-nums ${r.total_return >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}`}>
                      {formatPercent(r.total_return)}
                    </td>
                    <td className="px-3 py-2 tabular-nums">{formatNumber(r.sharpe_ratio)}</td>
                    <td className="px-3 py-2 tabular-nums text-[var(--danger)]">{formatPercent(-Math.abs(r.max_drawdown_pct))}</td>
                    <td className="px-3 py-2 tabular-nums">{formatPercent(r.win_rate, 1)}</td>
                    <td className="px-3 py-2 tabular-nums">{formatNumber(r.profit_factor)}</td>
                    <td className="px-3 py-2 tabular-nums">{r.total_trades}</td>
                    <td className={`px-3 py-2 tabular-nums ${(r.trades?.reduce((a, t) => a + (Number(t.pnl) || 0), 0) || 0) >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}`}>
                      {formatCurrency(r.trades?.reduce((a, t) => a + (Number(t.pnl) || 0), 0) || 0)}
                    </td>
                    <td className="px-3 py-2 tabular-nums">{formatCurrency(r.final_value)}</td>
                    <td className="px-3 py-2">
                      {r.error ? (
                        <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-300">
                          Failed
                        </span>
                      ) : (
                        <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-300">
                          OK
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedMultiIndex(i);
                        }}
                        disabled={!r.run_id}
                        className="rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-medium transition-colors hover:border-[var(--primary)] hover:text-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-40"
                        title={r.run_id ? "Show details" : "Detail unavailable (no run_id)"}
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedMultiResult && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 lg:col-span-1">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold">
                    {selectedMultiResult.symbol} - {selectedMultiResult.interval}
                  </h3>
                  {selectedMultiResult.error ? (
                    <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-300">
                      Failed
                    </span>
                  ) : (
                    <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-300">
                      Success
                    </span>
                  )}
                </div>

                {selectedMultiResult.error ? (
                  <div className="rounded-lg border border-red-500/50 bg-red-950/30 p-3 text-xs text-red-200">
                    {selectedMultiResult.error}
                  </div>
                ) : (
                  <div className="space-y-1.5 text-xs">
                    <div><span className="text-[var(--muted)]">Run ID: </span>{selectedMultiResult.run_id || "--"}</div>
                    <div><span className="text-[var(--muted)]">Return: </span><span className={selectedMultiResult.total_return >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}>{formatPercent(selectedMultiResult.total_return)}</span></div>
                    <div><span className="text-[var(--muted)]">Sharpe: </span>{formatNumber(selectedMultiResult.sharpe_ratio)}</div>
                    <div><span className="text-[var(--muted)]">Max DD: </span><span className="text-[var(--danger)]">{formatPercent(-Math.abs(selectedMultiResult.max_drawdown_pct))}</span></div>
                    <div><span className="text-[var(--muted)]">Win Rate: </span>{formatPercent(selectedMultiResult.win_rate, 1)}</div>
                    <div><span className="text-[var(--muted)]">PF: </span>{formatNumber(selectedMultiResult.profit_factor)}</div>
                    <div><span className="text-[var(--muted)]">Trades: </span>{selectedMultiResult.total_trades}</div>
                    <div><span className="text-[var(--muted)]">Final Value: </span>{formatCurrency(selectedMultiResult.final_value)}</div>
                  </div>
                )}
              </div>

              <div className="space-y-4 lg:col-span-2">
                {selectedMultiResult.run_id ? (
                  <>
                    {selectedMultiResult.equity_curve?.length ? (
                      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                        <h3 className="mb-2 text-sm font-semibold">Equity Curve</h3>
                        <EquityChart data={selectedMultiResult.equity_curve} />
                      </div>
                    ) : (
                      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm text-[var(--muted)]">
                        Equity curve data not available.
                      </div>
                    )}

                    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                      <h3 className="mb-2 text-sm font-semibold">
                        Trades ({selectedMultiResult.trades?.length ?? 0})
                      </h3>
                      {selectedMultiResult.trades?.length ? (
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
                              {selectedMultiResult.trades.map((t) => (
                                <tr key={`${selectedMultiResult.run_id}-${t.trade_num}`} className="border-b border-[var(--border)]/20">
                                  <td className="py-0.5">{t.trade_num}</td>
                                  <td className={t.direction === "LONG" ? "text-[var(--success)]" : "text-[var(--danger)]"}>{t.direction}</td>
                                  <td className={t.pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}>{formatCurrency(t.pnl)}</td>
                                  <td className={t.pnl_pct >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]"}>{formatPercent(t.pnl_pct)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="text-xs text-[var(--muted)]">No trades in this run.</p>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-sm text-[var(--muted)]">
                    Detail panels disabled because this row has no run_id.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
