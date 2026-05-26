/**
 * Typed API client for the FastAPI backend.
 */

// Browser-side calls should resolve from host machine.
// Fallback localhost prevents Docker-internal hostnames from leaking to browser.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error ${res.status}`);
  }
  return res.json();
}

function setQueryParam(
  qs: URLSearchParams,
  key: string,
  value: string | number | boolean | null | undefined
) {
  if (value === undefined || value === null || value === "") return;
  qs.set(key, String(value));
}

// ── Backtest ────────────────────────────────────────────

export interface BacktestRequest {
  strategy: string;
  symbol: string;
  source?: string;
  exchange?: string;
  interval?: string;
  n_bars?: number;
  initial_cash?: number;
  commission?: number;
  slippage_ticks?: number;
  strategy_params?: Record<string, number | boolean | string>;
  instant_execution?: boolean;
}

export interface TradeInfo {
  trade_num: number;
  direction: string;
  entry_time: string;
  entry_price: number;
  exit_time: string;
  exit_price: number;
  size: number;
  pnl: number;
  pnl_pct: number;
  commission: number;
  bars_held?: number;
}

export interface BacktestResult {
  run_id?: string;
  strategy: string;
  symbol: string;
  interval: string;
  total_return: number;
  sharpe_ratio: number;
  sortino_ratio?: number;
  max_drawdown_pct: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  sqn?: number;
  initial_cash: number;
  final_value: number;
  trades: TradeInfo[];
  equity_curve: { datetime: string; value: number }[];
  buy_hold_return?: number;
  parameters?: Record<string, number>;
  error?: string;
}

export interface BacktestHistoryItem {
  run_id: string;
  strategy_name: string;
  symbol: string;
  timeframe?: string;
  interval?: string;
  start_date?: string;
  end_date?: string;
  initial_cash?: number;
  final_value?: number;
  total_return?: number;
  sharpe_ratio?: number;
  sortino_ratio?: number;
  calmar_ratio?: number;
  max_drawdown?: number;
  max_drawdown_pct?: number;
  avg_drawdown?: number;
  win_rate?: number;
  total_trades?: number;
  won_trades?: number;
  lost_trades?: number;
  profit_factor?: number;
  avg_win?: number;
  avg_loss?: number;
  avg_trade?: number;
  sqn?: number;
  buy_hold_return?: number;
  parameters?: Record<string, unknown>;
  equity_curve_json?: { datetime: string; value: number }[];
  drawdown_curve_json?: { datetime: string; value: number }[];
  created_at?: string;
  trades?: TradeInfo[];
}

export const backtestApi = {
  run: (data: BacktestRequest) =>
    request<BacktestResult>("/api/backtest/run", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  runMulti: (data: {
    strategy: string;
    symbols: string[];
    intervals?: string[];
    [k: string]: unknown;
  }) =>
    request<{ results: BacktestResult[]; count: number }>(
      "/api/backtest/multi",
      { method: "POST", body: JSON.stringify(data) }
    ),

  analyzeMultiMatrix: (data: {
    strategy: string;
    symbols: string[];
    source?: string;
    exchange?: string;
    intervals?: string[];
    n_bars?: number;
    initial_cash?: number;
    commission?: number;
    slippage_ticks?: number;
    strategy_params?: Record<string, number | boolean | string>;
  }) =>
    request<{
      rows: Array<{
        symbol: string;
        interval: string;
        run_id: string;
        total_return: number;
        sharpe: number;
        max_dd: number;
        win_rate: number;
        pf: number;
        trades: number;
        status: "success" | "failed";
        error?: string;
      }>;
      summary: {
        total: number;
        success: number;
        failed: number;
        avg_return: number;
        avg_sharpe: number;
        best?: Record<string, unknown> | null;
        worst?: Record<string, unknown> | null;
      };
      failures: Array<{ symbol: string; interval: string; reason: string }>;
    }>("/api/backtest/multi/analyze", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getHistory: (params?: { limit?: number; strategy?: string; symbol?: string }) => {
    const qs = new URLSearchParams();
    setQueryParam(qs, "limit", params?.limit);
    setQueryParam(qs, "strategy", params?.strategy);
    setQueryParam(qs, "symbol", params?.symbol);
    const query = qs.toString();
    return request<BacktestHistoryItem[]>(
      `/api/backtest/history${query ? `?${query}` : ""}`
    );
  },

  getHistoryDetail: (runId: string) =>
    request<BacktestHistoryItem>(`/api/backtest/history/${runId}`),

  deleteHistory: (runId: string) =>
    request<{ deleted: boolean }>(`/api/backtest/history/${runId}`, { method: "DELETE" }),

  deleteAllHistory: () =>
    request<{ deleted: number }>("/api/backtest/history", { method: "DELETE" }),
};

// ── Strategies ──────────────────────────────────────────

export interface StrategyInfo {
  name: string;
  class_name: string;
  description?: string;
  category: string;
  params: Record<string, number | string | boolean>;
}

export const strategiesApi = {
  list: () => request<StrategyInfo[]>("/api/strategies"),
  getParams: (name: string) =>
    request<{
      strategy: string;
      class_name: string;
      params: { name: string; default: number; param_type: string }[];
    }>(`/api/strategies/${name}/params`),
};

// ── Data ────────────────────────────────────────────────

export interface DataSummaryItem {
  symbol: string;
  exchange?: string;
  timeframe: string;
  bars: number;
  first_date: string;
  last_date: string;
}

export const dataApi = {
  download: (data: {
    symbol: string;
    source?: string;
    exchange?: string;
    interval?: string;
    n_bars?: number;
  }) =>
    request<{
      symbol: string;
      bars_downloaded: number;
      interval: string;
      success: boolean;
      error?: string;
    }>("/api/data/download", { method: "POST", body: JSON.stringify(data) }),

  bulkDownload: (data: {
    symbols: string[];
    source?: string;
    exchange?: string;
    interval: string;
    n_bars: number;
  }) =>
    request<{
      results: { symbol: string; bars_downloaded: number; interval: string; success: boolean; error?: string }[];
      total: number;
      success_count: number;
    }>("/api/data/download/bulk", { method: "POST", body: JSON.stringify(data) }),

  getSymbols: () =>
    request<{ symbol: string; exchange?: string; intervals: string[]; bar_count: number }[]>(
      "/api/data/symbols"
    ),

  getSummary: () => request<DataSummaryItem[]>("/api/data/summary"),
};

// ── Scraper ─────────────────────────────────────────────

export interface RawPost {
  hash_id: string;
  reddit_id?: string;
  subreddit?: string;
  title?: string;
  content?: string;
  url?: string;
  score: number;
  comments: number;
  author?: string;
  post_created_at?: string;
  collected_at?: string;
  ai_processed: boolean;
  stage1_category?: string;
  stage1_processed_at?: string;
  strategy_id?: number;
  strategy_name?: string;
  entry_rules?: string;
  exit_rules?: string;
  strategy_indicators?: string[];
  tp_pct?: number;
  sl_pct?: number;
  ai_score?: number;
  strategy_timeframe?: string;
  strategy_summary?: string;
  strategy_status?: string;
  approval_status?: string;
  execution_status?: string;
  fix_category?: string;
  strategy_category?: string;
  rule_quality?: "weak" | "medium" | "strong" | string;
}

export interface PaginatedPosts {
  posts: RawPost[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AnalyzeSingleResult {
  hash_id: string;
  category: string;
  strategy_saved: boolean;
  insight_saved: boolean;
  strategy_name?: string;
  ai_score: number;
}

export interface AnalyzeResult {
  total_analyzed: number;
  actionable: number;
  methodology: number;
  noise: number;
  total_cost_usd: number;
}

export interface SubredditPreset {
  name: string;
  priority: number;
  min_score: number;
  min_length: number;
  enabled: boolean;
  tags: string[];
}

export interface SubredditPresetsResponse {
  tiers: Record<string, SubredditPreset[]>;
  settings: Record<string, unknown>;
}

export const scraperApi = {
  getSubreddits: () =>
    request<SubredditPresetsResponse>("/api/scraper/subreddits"),

  collectReddit: (data: {
    subreddits?: string[];
    limit?: number;
    min_score?: number;
  }) =>
    request<{
      total_collected: number;
      new_posts: number;
      duplicates: number;
    }>("/api/scraper/reddit/collect", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  collectRedditStream: (data: {
    subreddits: string[];
    limit?: number;
    min_score?: number;
    time_filter?: string;
  }) =>
    fetch(`${API_BASE}/api/scraper/reddit/collect-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  analyzeReddit: (data: { batch_size?: number }) =>
    request<AnalyzeResult>("/api/scraper/reddit/analyze", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getPosts: (params: {
    page?: number;
    page_size?: number;
    filter?: string;
    search?: string;
    category?: string;
    min_post_score?: number;
    min_ai_score?: number;
    has_strategy?: boolean;
    has_entry_rules?: boolean;
    has_exit_rules?: boolean;
  }) => {
    const qs = new URLSearchParams();
    setQueryParam(qs, "page", params.page);
    setQueryParam(qs, "page_size", params.page_size);
    setQueryParam(qs, "filter", params.filter);
    setQueryParam(qs, "search", params.search);
    setQueryParam(qs, "category", params.category);
    setQueryParam(qs, "min_post_score", params.min_post_score);
    setQueryParam(qs, "min_ai_score", params.min_ai_score);
    setQueryParam(qs, "has_strategy", params.has_strategy);
    setQueryParam(qs, "has_entry_rules", params.has_entry_rules);
    setQueryParam(qs, "has_exit_rules", params.has_exit_rules);
    const query = qs.toString();
    return request<PaginatedPosts>(`/api/scraper/posts${query ? `?${query}` : ""}`);
  },

  analyzePost: (hashId: string) =>
    request<AnalyzeSingleResult>(`/api/scraper/posts/${hashId}/analyze`, {
      method: "POST",
    }),

  analyzeBatch: (batchSize: number) =>
    request<AnalyzeResult>("/api/scraper/posts/analyze-batch", {
      method: "POST",
      body: JSON.stringify({ batch_size: batchSize }),
    }),

  analyzeBatchStream: (batchSize: number) =>
    fetch(`${API_BASE}/api/scraper/posts/analyze-batch-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ batch_size: batchSize }),
    }),

  searchGithub: (data: {
    query?: string;
    language?: string;
    min_stars?: number;
    max_repos?: number;
  }) =>
    request<{
      repos_found: number;
      strategies_detected: number;
      new_strategies: number;
    }>("/api/scraper/github/search", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getStrategies: (params?: {
    page?: number;
    page_size?: number;
    search?: string;
    category?: string;
    status?: string;
    min_score?: number;
    max_score?: number;
    has_entry_rules?: boolean;
    has_exit_rules?: boolean;
    timeframe?: string;
    sort_by?: string;
    sort_dir?: "asc" | "desc";
  }) => {
    const qs = new URLSearchParams();
    setQueryParam(qs, "page", params?.page);
    setQueryParam(qs, "page_size", params?.page_size);
    setQueryParam(qs, "search", params?.search);
    setQueryParam(qs, "category", params?.category);
    setQueryParam(qs, "min_score", params?.min_score);
    setQueryParam(qs, "max_score", params?.max_score);
    setQueryParam(qs, "status", params?.status);
    setQueryParam(qs, "has_entry_rules", params?.has_entry_rules);
    setQueryParam(qs, "has_exit_rules", params?.has_exit_rules);
    setQueryParam(qs, "timeframe", params?.timeframe);
    setQueryParam(qs, "sort_by", params?.sort_by);
    setQueryParam(qs, "sort_dir", params?.sort_dir);
    return request<{
      strategies: Record<string, unknown>[];
      total: number;
      page: number;
      page_size: number;
      total_pages: number;
    }>(
      `/api/scraper/strategies?${qs.toString()}`
    );
  },

  approveActionable: (data: { strategy_id: number; approved?: boolean }) =>
    request<{ strategy_id: number; status: string }>("/api/scraper/actionable/approve", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  approveActionableBulk: (data: { limit: number; min_score?: number }) =>
    request<{ requested: number; approved_count: number; strategy_ids: number[] }>(
      "/api/scraper/actionable/approve-bulk",
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),

  convertAndTestActionable: (data: {
    strategy_ids?: number[];
    first_n?: number;
    only_approved?: boolean;
    symbols?: string[];
    intervals?: string[];
    n_bars?: number;
  }) =>
    request<{
      total: number;
      ready_to_use: number;
      needs_fix: number;
      results: Record<string, unknown>[];
    }>("/api/scraper/actionable/convert-and-test", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  convertAndTestActionableStream: (data: {
    strategy_ids?: number[];
    first_n?: number;
    only_approved?: boolean;
    symbols?: string[];
    intervals?: string[];
    n_bars?: number;
  }) =>
    fetch(`${API_BASE}/api/scraper/actionable/convert-and-test-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
};

// ── Converter ───────────────────────────────────────────

export const converterApi = {
  convert: (data: { code: string; direction?: string; model?: string }) =>
    request<{
      converted_code: string;
      direction: string;
      model_used: string;
      tokens_used: number;
      cost_usd: number;
      is_valid: boolean;
      validation_error?: string;
    }>("/api/converter/pine-to-python", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ── Health ──────────────────────────────────────────────

export const healthApi = {
  check: () => request<{ status: string; service: string }>("/health"),
};
