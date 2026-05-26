"use client";

import { useState, useCallback, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { scraperApi, type RawPost, type SubredditPreset } from "@/lib/api";
import { MetricCard } from "@/components/ui/metric-card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const FILTER_TABS = [
  { key: "all", label: "All" },
  { key: "unanalyzed", label: "Unanalyzed" },
  { key: "analyzed", label: "Analyzed" },
] as const;

const CATEGORY_COLORS: Record<string, string> = {
  ACTIONABLE_STRATEGY: "bg-green-500/20 text-green-400",
  METHODOLOGY: "bg-blue-500/20 text-blue-400",
  INSIGHT: "bg-purple-500/20 text-purple-400",
  NOISE: "bg-neutral-500/20 text-neutral-400",
  SKIP: "bg-neutral-500/20 text-neutral-500",
  POSITION_SHARE: "bg-yellow-500/20 text-yellow-400",
};

const CATEGORY_FILTERS = [
  "all",
  "ACTIONABLE_STRATEGY",
  "METHODOLOGY",
  "INSIGHT",
  "NOISE",
  "SKIP",
  "POSITION_SHARE",
] as const;

type BoolFilter = "all" | "yes" | "no";

interface StreamProgress {
  current: number;
  total: number;
  hash_id?: string;
  title?: string;
  category?: string;
  strategy_name?: string;
  error?: string;
  done: boolean;
  actionable?: number;
  methodology?: number;
  noise?: number;
}

function CategoryBadge({ category }: { category?: string | null }) {
  if (!category) return <span className="text-xs text-[var(--muted)]">--</span>;
  const cls = CATEGORY_COLORS[category] || "bg-neutral-500/20 text-neutral-400";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {category}
    </span>
  );
}

function StatusDot({ analyzed }: { analyzed: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${
        analyzed ? "bg-green-500" : "bg-amber-500"
      }`}
      title={analyzed ? "Analyzed" : "Pending"}
    />
  );
}

export default function DiscoveryPage() {
  const queryClient = useQueryClient();
  const [mainTab, setMainTab] = useState<"posts" | "collect">("posts");
  const [filter, setFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [minScoreFilter, setMinScoreFilter] = useState<string>("");
  const [hasStrategyFilter, setHasStrategyFilter] = useState<BoolFilter>("all");
  const [hasEntryRulesFilter, setHasEntryRulesFilter] = useState<BoolFilter>("all");
  const [hasExitRulesFilter, setHasExitRulesFilter] = useState<BoolFilter>("all");
  const [batchSize, setBatchSize] = useState(10);
  const [pipelineCount, setPipelineCount] = useState(10);
  const [pipelineMinScore, setPipelineMinScore] = useState(60);
  const [pipelineProgress, setPipelineProgress] = useState<{
    current: number;
    total: number;
    strategy_name?: string;
    status?: string;
    reason?: string;
    done?: boolean;
    ready_to_use?: number;
    needs_fix?: number;
  } | null>(null);
  const [isPipelineRunning, setIsPipelineRunning] = useState(false);
  const [expandedPost, setExpandedPost] = useState<string | null>(null);

  const [selectedSubs, setSelectedSubs] = useState<string[]>(["algotrading"]);
  const [customSubInput, setCustomSubInput] = useState("");
  const [collectLimit, setCollectLimit] = useState(25);
  const [collectTimeFilter, setCollectTimeFilter] = useState("week");
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);

  const [collectProgress, setCollectProgress] = useState<{
    current: number;
    total: number;
    subreddit?: string;
    new_posts?: number;
    duplicates?: number;
    error?: string;
    done: boolean;
    total_collected?: number;
  } | null>(null);
  const [collectResults, setCollectResults] = useState<
    { subreddit: string; new_posts: number; duplicates: number; error?: string }[]
  >([]);
  const [isCollecting, setIsCollecting] = useState(false);
  const collectAbortRef = useRef<AbortController | null>(null);

  const [streamProgress, setStreamProgress] = useState<StreamProgress | null>(null);
  const [streamResults, setStreamResults] = useState<StreamProgress[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const boolFilterToParam = (v: BoolFilter): boolean | undefined =>
    v === "yes" ? true : v === "no" ? false : undefined;

  const postsQuery = useQuery({
    queryKey: [
      "posts",
      page,
      pageSize,
      filter,
      search,
      categoryFilter,
      minScoreFilter,
      hasStrategyFilter,
      hasEntryRulesFilter,
      hasExitRulesFilter,
    ],
    queryFn: () =>
      scraperApi.getPosts({
        page,
        page_size: pageSize,
        filter: filter === "all" ? undefined : filter,
        search: search || undefined,
        category: categoryFilter === "all" ? undefined : categoryFilter,
        min_post_score: minScoreFilter === "" ? undefined : Number(minScoreFilter),
        has_strategy: boolFilterToParam(hasStrategyFilter),
        has_entry_rules: boolFilterToParam(hasEntryRulesFilter),
        has_exit_rules: boolFilterToParam(hasExitRulesFilter),
      }),
  });

  const subredditPresetsQuery = useQuery({
    queryKey: ["subreddit-presets"],
    queryFn: scraperApi.getSubreddits,
    staleTime: 5 * 60 * 1000,
  });

  const collectMutation = useMutation({
    mutationFn: scraperApi.collectReddit,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["posts"] }),
  });

  const analyzeSingleMutation = useMutation({
    mutationFn: scraperApi.analyzePost,
    onSuccess: () => {
      setAnalyzingId(null);
      queryClient.invalidateQueries({ queryKey: ["posts"] });
    },
    onError: () => setAnalyzingId(null),
  });

  const approveSingleMutation = useMutation({
    mutationFn: (strategyId: number) =>
      scraperApi.approveActionable({ strategy_id: strategyId, approved: true }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["posts"] }),
  });

  const approveBulkMutation = useMutation({
    mutationFn: () =>
      scraperApi.approveActionableBulk({ limit: pipelineCount, min_score: pipelineMinScore }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["posts"] }),
  });

  const handleBatchStream = useCallback(async () => {
    setIsStreaming(true);
    setStreamResults([]);
    setStreamProgress({ current: 0, total: batchSize, done: false });

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_BASE}/api/scraper/posts/analyze-batch-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ batch_size: batchSize }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`Stream failed: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data: StreamProgress = JSON.parse(line.slice(6));
              setStreamProgress(data);
              if (!data.done) {
                setStreamResults((prev) => [...prev, data]);
              }
            } catch {
              // skip malformed lines
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setStreamProgress((prev) => prev ? { ...prev, done: true, error: (err as Error).message } : null);
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      queryClient.invalidateQueries({ queryKey: ["posts"] });
    }
  }, [batchSize, queryClient]);

  const handleActionablePipeline = useCallback(async () => {
    setIsPipelineRunning(true);
    setPipelineProgress({ current: 0, total: pipelineCount, done: false });
    try {
      await scraperApi.approveActionableBulk({
        limit: pipelineCount,
        min_score: pipelineMinScore,
      });

      const res = await scraperApi.convertAndTestActionableStream({
        first_n: pipelineCount,
        only_approved: true,
      });
      if (!res.ok || !res.body) throw new Error(`Pipeline stream failed: ${res.status}`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            setPipelineProgress(data);
          } catch {
            // ignore malformed events
          }
        }
      }
    } catch (err) {
      setPipelineProgress((prev) => ({
        ...(prev || { current: 0, total: pipelineCount }),
        done: true,
        status: "error",
        reason: (err as Error).message,
      }));
    } finally {
      setIsPipelineRunning(false);
      queryClient.invalidateQueries({ queryKey: ["posts"] });
    }
  }, [pipelineCount, pipelineMinScore, queryClient]);

  const handleCollectStream = useCallback(async () => {
    if (selectedSubs.length === 0) return;
    setIsCollecting(true);
    setCollectResults([]);
    setCollectProgress({ current: 0, total: selectedSubs.length, done: false });

    const controller = new AbortController();
    collectAbortRef.current = controller;

    try {
      const res = await scraperApi.collectRedditStream({
        subreddits: selectedSubs,
        limit: collectLimit,
        time_filter: collectTimeFilter,
      });

      if (!res.ok || !res.body) throw new Error(`Stream failed: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            setCollectProgress(data);
            if (!data.done && data.subreddit) {
              setCollectResults((prev) => [
                ...prev,
                {
                  subreddit: data.subreddit,
                  new_posts: data.new_posts ?? 0,
                  duplicates: data.duplicates ?? 0,
                  error: data.error,
                },
              ]);
            }
          } catch {
            // skip malformed
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setCollectProgress((prev) =>
          prev ? { ...prev, done: true, error: (err as Error).message } : null
        );
      }
    } finally {
      setIsCollecting(false);
      collectAbortRef.current = null;
      queryClient.invalidateQueries({ queryKey: ["posts"] });
    }
  }, [selectedSubs, collectLimit, collectTimeFilter, queryClient]);

  const toggleSub = useCallback((name: string) => {
    setSelectedSubs((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]
    );
  }, []);

  const addCustomSub = useCallback(() => {
    const name = customSubInput.trim().replace(/^r\//, "");
    if (name && !selectedSubs.includes(name)) {
      setSelectedSubs((prev) => [...prev, name]);
    }
    setCustomSubInput("");
  }, [customSubInput, selectedSubs]);

  const posts = postsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Strategy Discovery</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {posts ? `${posts.total} posts in database` : "Loading..."}
          </p>
        </div>
      </div>

      {/* Main tabs */}
      <div className="flex gap-2 border-b border-[var(--border)]">
        <button
          onClick={() => setMainTab("posts")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            mainTab === "posts"
              ? "border-b-2 border-[var(--primary)] text-[var(--primary)]"
              : "text-[var(--muted)] hover:text-[var(--foreground)]"
          }`}
        >
          Posts Database
        </button>
        <button
          onClick={() => setMainTab("collect")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            mainTab === "collect"
              ? "border-b-2 border-[var(--primary)] text-[var(--primary)]"
              : "text-[var(--muted)] hover:text-[var(--foreground)]"
          }`}
        >
          Collect New
        </button>
      </div>

      {mainTab === "posts" && (
        <div className="space-y-4">
          {/* Actionable approval/conversion pipeline */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <p className="text-sm font-medium">Actionable Approval Pipeline</p>
                <p className="text-xs text-[var(--muted)]">
                  İlk N actionable stratejiyi onayla, koda dönüştür ve çoklu sembol/TF auto-backtest çalıştır.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => { setCategoryFilter("ACTIONABLE_STRATEGY"); setPage(1); }}
                  className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--border)]"
                >
                  Actionable Filter
                </button>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={pipelineCount}
                  onChange={(e) => setPipelineCount(Math.max(1, Math.min(500, Number(e.target.value) || 1)))}
                  className="w-24 rounded-lg border border-[var(--border)] bg-transparent px-2 py-1.5 text-xs"
                  title="First N strategies"
                />
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={pipelineMinScore}
                  onChange={(e) => setPipelineMinScore(Math.max(0, Math.min(100, Number(e.target.value) || 0)))}
                  className="w-24 rounded-lg border border-[var(--border)] bg-transparent px-2 py-1.5 text-xs"
                  title="Min AI score"
                />
                <button
                  onClick={() => approveBulkMutation.mutate()}
                  disabled={approveBulkMutation.isPending || isPipelineRunning}
                  className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--border)] disabled:opacity-50"
                >
                  {approveBulkMutation.isPending ? "Approving..." : "Approve Bulk"}
                </button>
                <button
                  onClick={handleActionablePipeline}
                  disabled={isPipelineRunning}
                  className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                >
                  {isPipelineRunning ? "Running..." : "Approve + Convert + Test"}
                </button>
              </div>
            </div>

            {pipelineProgress && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[var(--muted)]">
                    {pipelineProgress.done
                      ? `Done — Ready: ${pipelineProgress.ready_to_use || 0}, Needs Fix: ${pipelineProgress.needs_fix || 0}${pipelineProgress.reason ? ` (${pipelineProgress.reason})` : ""}`
                      : `Processing ${pipelineProgress.current}/${pipelineProgress.total}: ${pipelineProgress.strategy_name || "..."}`}
                  </span>
                  <span className="font-mono text-[var(--muted)]">
                    {pipelineProgress.total > 0
                      ? `${Math.round((pipelineProgress.current / pipelineProgress.total) * 100)}%`
                      : "0%"}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      pipelineProgress.done ? "bg-green-500" : "bg-[var(--primary)]"
                    }`}
                    style={{
                      width:
                        pipelineProgress.total > 0
                          ? `${(pipelineProgress.current / pipelineProgress.total) * 100}%`
                          : "0%",
                    }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Batch analyze bar */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">Batch Analyze</span>
              <input
                type="number"
                value={batchSize}
                onChange={(e) => setBatchSize(Math.max(1, Math.min(50, +e.target.value)))}
                className="w-20 rounded-lg border border-[var(--border)] bg-transparent px-2 py-1.5 text-sm"
                min={1}
                max={50}
              />
              <span className="text-xs text-[var(--muted)]">unanalyzed posts</span>
              <button
                onClick={handleBatchStream}
                disabled={isStreaming}
                className="rounded-lg bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {isStreaming ? "Stop" : "Run Batch"}
              </button>
              {isStreaming && (
                <button
                  onClick={() => abortRef.current?.abort()}
                  className="rounded-lg border border-red-500/50 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10"
                >
                  Cancel
                </button>
              )}
            </div>

            {/* Progress bar */}
            {streamProgress && (streamProgress.total > 0 || isStreaming) && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[var(--muted)]">
                    {streamProgress.done
                      ? `Completed: ${streamProgress.actionable || 0} actionable, ${streamProgress.methodology || 0} methodology, ${streamProgress.noise || 0} noise`
                      : `Analyzing ${streamProgress.current}/${streamProgress.total}: "${streamProgress.title || "..."}"`}
                  </span>
                  <span className="font-mono text-[var(--muted)]">
                    {streamProgress.total > 0
                      ? `${Math.round((streamProgress.current / streamProgress.total) * 100)}%`
                      : "0%"}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      streamProgress.done ? "bg-green-500" : "bg-[var(--primary)]"
                    }`}
                    style={{
                      width: streamProgress.total > 0
                        ? `${(streamProgress.current / streamProgress.total) * 100}%`
                        : "0%",
                    }}
                  />
                </div>

                {/* Per-post results feed */}
                {streamResults.length > 0 && (
                  <div className="max-h-32 overflow-y-auto rounded-lg bg-[var(--background)] p-2 text-xs space-y-0.5">
                    {streamResults.map((r, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <span className={`inline-block h-1.5 w-1.5 rounded-full ${
                          r.category === "ACTIONABLE_STRATEGY" ? "bg-green-500"
                          : r.category === "METHODOLOGY" ? "bg-blue-500"
                          : r.category === "INSIGHT" ? "bg-purple-500"
                          : "bg-neutral-500"
                        }`} />
                        <span className="text-[var(--muted)] tabular-nums">{r.current}.</span>
                        <span className="truncate flex-1">{r.title}</span>
                        <CategoryBadge category={r.category} />
                        {r.strategy_name && (
                          <span className="text-green-400 truncate max-w-[200px]">{r.strategy_name}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Filter tabs + search */}
          <div className="space-y-3">
            <div className="flex items-center gap-4">
            <div className="flex gap-1 rounded-lg border border-[var(--border)] p-0.5">
              {FILTER_TABS.map((t) => (
                <button
                  key={t.key}
                  onClick={() => { setFilter(t.key); setPage(1); }}
                  className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                    filter === t.key
                      ? "bg-[var(--primary)] text-white"
                      : "text-[var(--muted)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => { e.preventDefault(); setSearch(searchInput); setPage(1); }}
              className="flex flex-1 gap-2"
            >
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search by title or subreddit..."
                className="flex-1 rounded-lg border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm"
              />
              <button
                type="submit"
                className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--border)]"
              >
                Search
              </button>
              {search && (
                <button
                  type="button"
                  onClick={() => { setSearch(""); setSearchInput(""); setPage(1); }}
                  className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--border)]"
                >
                  Clear
                </button>
              )}
            </form>
          </div>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
              <select
                value={categoryFilter}
                onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
                className="rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-xs"
              >
                {CATEGORY_FILTERS.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat === "all" ? "All Categories" : cat}
                  </option>
                ))}
              </select>
              <input
                type="number"
                min={0}
                max={100}
                value={minScoreFilter}
                onChange={(e) => { setMinScoreFilter(e.target.value); setPage(1); }}
                placeholder="Min score"
                className="rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-xs"
              />
              <select
                value={hasStrategyFilter}
                onChange={(e) => { setHasStrategyFilter(e.target.value as BoolFilter); setPage(1); }}
                className="rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-xs"
              >
                <option value="all">Strategy: All</option>
                <option value="yes">Strategy: Yes</option>
                <option value="no">Strategy: No</option>
              </select>
              <select
                value={hasEntryRulesFilter}
                onChange={(e) => { setHasEntryRulesFilter(e.target.value as BoolFilter); setPage(1); }}
                className="rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-xs"
              >
                <option value="all">Entry rules: All</option>
                <option value="yes">Entry rules: Yes</option>
                <option value="no">Entry rules: No</option>
              </select>
              <select
                value={hasExitRulesFilter}
                onChange={(e) => { setHasExitRulesFilter(e.target.value as BoolFilter); setPage(1); }}
                className="rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-xs"
              >
                <option value="all">Exit rules: All</option>
                <option value="yes">Exit rules: Yes</option>
                <option value="no">Exit rules: No</option>
              </select>
            </div>
          </div>

          {/* Posts table */}
          <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--card)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
                  <th className="w-8 px-3 py-2.5" />
                  <th className="px-3 py-2.5">Title</th>
                  <th className="px-3 py-2.5">Subreddit</th>
                  <th className="px-3 py-2.5 text-right">Score</th>
                  <th className="px-3 py-2.5">Category</th>
                  <th className="px-3 py-2.5">Strategy</th>
                  <th className="px-3 py-2.5">Entry Rules</th>
                  <th className="px-3 py-2.5">Exit Rules</th>
                  <th className="px-3 py-2.5">Pipeline</th>
                  <th className="px-3 py-2.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {postsQuery.isLoading && (
                  <tr>
                    <td colSpan={10} className="py-12 text-center text-[var(--muted)]">
                      Loading posts...
                    </td>
                  </tr>
                )}
                {postsQuery.isError && (
                  <tr>
                    <td colSpan={10} className="py-12 text-center text-red-400">
                      Failed to load posts: {(postsQuery.error as Error).message}
                    </td>
                  </tr>
                )}
                {posts?.posts.map((post: RawPost) => (
                  <PostRow
                    key={post.hash_id}
                    post={post}
                    analyzing={analyzingId === post.hash_id && analyzeSingleMutation.isPending}
                    approving={approveSingleMutation.isPending}
                    expanded={expandedPost === post.hash_id}
                    onToggleExpand={() =>
                      setExpandedPost(expandedPost === post.hash_id ? null : post.hash_id)
                    }
                    onAnalyze={() => {
                      setAnalyzingId(post.hash_id);
                      analyzeSingleMutation.mutate(post.hash_id);
                    }}
                    onApprove={() => {
                      if (!post.strategy_id) return;
                      approveSingleMutation.mutate(post.strategy_id);
                    }}
                  />
                ))}
                {posts && posts.posts.length === 0 && (
                  <tr>
                    <td colSpan={10} className="py-12 text-center text-[var(--muted)]">
                      No posts found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {posts && posts.total_pages > 1 && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-[var(--muted)]">
                Page {posts.page} of {posts.total_pages} ({posts.total} total)
              </span>
              <div className="flex gap-1">
                <button
                  disabled={posts.page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="rounded-lg border border-[var(--border)] px-3 py-1 disabled:opacity-30"
                >
                  Prev
                </button>
                {Array.from({ length: Math.min(5, posts.total_pages) }, (_, i) => {
                  const start = Math.max(1, Math.min(posts.page - 2, posts.total_pages - 4));
                  const n = start + i;
                  if (n > posts.total_pages) return null;
                  return (
                    <button
                      key={n}
                      onClick={() => setPage(n)}
                      className={`rounded-lg border px-3 py-1 ${
                        n === posts.page
                          ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                          : "border-[var(--border)] hover:bg-[var(--border)]"
                      }`}
                    >
                      {n}
                    </button>
                  );
                })}
                <button
                  disabled={posts.page >= posts.total_pages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-lg border border-[var(--border)] px-3 py-1 disabled:opacity-30"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {mainTab === "collect" && (
        <div className="space-y-4">
          {/* Selected subreddits */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Reddit Collector</h2>
              <span className="text-xs text-[var(--muted)]">
                {selectedSubs.length} subreddit{selectedSubs.length !== 1 ? "s" : ""} selected
              </span>
            </div>

            {/* Selected chips */}
            {selectedSubs.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {selectedSubs.map((sub) => (
                  <span
                    key={sub}
                    className="inline-flex items-center gap-1 rounded-full bg-[var(--primary)]/15 px-2.5 py-1 text-xs font-medium text-[var(--primary)]"
                  >
                    r/{sub}
                    <button
                      onClick={() => toggleSub(sub)}
                      className="ml-0.5 rounded-full p-0.5 hover:bg-[var(--primary)]/20"
                    >
                      <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M3 3l6 6M9 3l-6 6" />
                      </svg>
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* Preset subreddits by tier */}
            {subredditPresetsQuery.data && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-[var(--muted)] uppercase tracking-wider">
                    Preset Subreddits
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        const all = Object.values(subredditPresetsQuery.data!.tiers)
                          .flat()
                          .filter((s) => s.enabled)
                          .map((s) => s.name);
                        setSelectedSubs(all);
                      }}
                      className="text-xs text-[var(--muted)] hover:text-[var(--foreground)]"
                    >
                      Select All Enabled
                    </button>
                    <span className="text-[var(--border)]">|</span>
                    <button
                      onClick={() => setSelectedSubs([])}
                      className="text-xs text-[var(--muted)] hover:text-red-400"
                    >
                      Clear All
                    </button>
                  </div>
                </div>

                {Object.entries(subredditPresetsQuery.data.tiers).map(([tier, subs]) => {
                  const tierLabel: Record<string, string> = {
                    high_quality: "High Quality",
                    medium_quality: "Medium Quality",
                    lower_quality: "Lower Quality",
                    experimental: "Experimental",
                  };
                  const tierColor: Record<string, string> = {
                    high_quality: "text-green-400",
                    medium_quality: "text-blue-400",
                    lower_quality: "text-yellow-400",
                    experimental: "text-neutral-500",
                  };
                  return (
                    <div key={tier} className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-medium ${tierColor[tier] || "text-[var(--muted)]"}`}>
                          {tierLabel[tier] || tier}
                        </span>
                        <button
                          onClick={() => {
                            const tierNames = (subs as SubredditPreset[]).filter((s) => s.enabled).map((s) => s.name);
                            const allSelected = tierNames.every((n) => selectedSubs.includes(n));
                            if (allSelected) {
                              setSelectedSubs((prev) => prev.filter((s) => !tierNames.includes(s)));
                            } else {
                              setSelectedSubs((prev) => [...new Set([...prev, ...tierNames])]);
                            }
                          }}
                          className="text-[10px] text-[var(--muted)] hover:text-[var(--foreground)]"
                        >
                          toggle all
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {(subs as SubredditPreset[]).map((sub) => {
                          const isSelected = selectedSubs.includes(sub.name);
                          const isDisabled = !sub.enabled;
                          return (
                            <button
                              key={sub.name}
                              onClick={() => toggleSub(sub.name)}
                              disabled={isDisabled}
                              title={
                                isDisabled
                                  ? `Disabled – ${sub.tags?.join(", ") || ""}`
                                  : `Priority ${sub.priority} · min score ${sub.min_score} · ${sub.tags?.join(", ") || ""}`
                              }
                              className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition-all ${
                                isDisabled
                                  ? "border-[var(--border)]/50 text-neutral-600 cursor-not-allowed opacity-40"
                                  : isSelected
                                  ? "border-[var(--primary)] bg-[var(--primary)]/15 text-[var(--primary)]"
                                  : "border-[var(--border)] text-[var(--muted)] hover:border-[var(--primary)]/50 hover:text-[var(--foreground)]"
                              }`}
                            >
                              {isSelected && (
                                <svg className="mr-1 -ml-0.5 inline h-3 w-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M2.5 6l2.5 2.5 4.5-5" />
                                </svg>
                              )}
                              r/{sub.name}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {subredditPresetsQuery.isLoading && (
              <p className="text-xs text-[var(--muted)]">Loading presets...</p>
            )}

            {/* Custom subreddit input */}
            <div className="space-y-1.5">
              <span className="text-xs font-medium text-[var(--muted)] uppercase tracking-wider">
                Custom Subreddit
              </span>
              <div className="flex gap-2">
                <div className="relative flex-1 max-w-xs">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-[var(--muted)]">r/</span>
                  <input
                    value={customSubInput}
                    onChange={(e) => setCustomSubInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustomSub(); } }}
                    placeholder="subreddit name"
                    className="w-full rounded-lg border border-[var(--border)] bg-transparent pl-8 pr-3 py-1.5 text-sm"
                  />
                </div>
                <button
                  onClick={addCustomSub}
                  disabled={!customSubInput.trim()}
                  className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--border)] disabled:opacity-30"
                >
                  + Add
                </button>
              </div>
            </div>

            {/* Collection settings + run */}
            <div className="flex flex-wrap items-end gap-3 border-t border-[var(--border)] pt-4">
              <label className="space-y-1">
                <span className="text-xs text-[var(--muted)]">Posts per subreddit</span>
                <input
                  type="number"
                  value={collectLimit}
                  onChange={(e) => setCollectLimit(Math.max(1, Math.min(100, +e.target.value)))}
                  className="w-20 rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-sm"
                  min={1}
                  max={100}
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--muted)]">Time filter</span>
                <select
                  value={collectTimeFilter}
                  onChange={(e) => setCollectTimeFilter(e.target.value)}
                  className="rounded-lg border border-[var(--border)] bg-transparent px-2.5 py-1.5 text-sm"
                >
                  <option value="day">Today</option>
                  <option value="week">This Week</option>
                  <option value="month">This Month</option>
                  <option value="year">This Year</option>
                  <option value="all">All Time</option>
                </select>
              </label>
              <div className="flex gap-2 ml-auto">
                {isCollecting && (
                  <button
                    onClick={() => collectAbortRef.current?.abort()}
                    className="rounded-lg border border-red-500/50 px-3 py-1.5 text-sm text-red-400 hover:bg-red-500/10"
                  >
                    Cancel
                  </button>
                )}
                <button
                  onClick={handleCollectStream}
                  disabled={isCollecting || selectedSubs.length === 0}
                  className="rounded-lg bg-[var(--primary)] px-5 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                >
                  {isCollecting ? "Collecting..." : "Collect Posts"}
                </button>
              </div>
            </div>
          </div>

          {/* Collect progress & results */}
          {(collectProgress || collectResults.length > 0) && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
              {/* Progress bar */}
              {collectProgress && (collectProgress.total > 0 || isCollecting) && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[var(--muted)]">
                      {collectProgress.done
                        ? `Done — ${collectProgress.new_posts ?? 0} new posts, ${collectProgress.duplicates ?? 0} duplicates`
                        : `Collecting r/${collectProgress.subreddit || "..."} (${collectProgress.current}/${collectProgress.total})`}
                    </span>
                    <span className="font-mono text-[var(--muted)]">
                      {collectProgress.total > 0
                        ? `${Math.round((collectProgress.current / collectProgress.total) * 100)}%`
                        : "0%"}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        collectProgress.done ? "bg-green-500" : "bg-[var(--primary)]"
                      }`}
                      style={{
                        width:
                          collectProgress.total > 0
                            ? `${(collectProgress.current / collectProgress.total) * 100}%`
                            : "0%",
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Per-subreddit results log */}
              {collectResults.length > 0 && (
                <div className="max-h-48 overflow-y-auto rounded-lg bg-[var(--background)] p-3 font-mono text-xs space-y-1">
                  {collectResults.map((r, i) => (
                    <div key={i} className="flex items-center gap-2">
                      {r.error ? (
                        <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
                      ) : (
                        <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
                      )}
                      <span className="text-[var(--muted)] w-5 text-right">{i + 1}.</span>
                      <span className="text-[var(--foreground)] min-w-[140px]">r/{r.subreddit}</span>
                      {r.error ? (
                        <span className="text-red-400 truncate">{r.error}</span>
                      ) : (
                        <>
                          <span className="text-green-400">{r.new_posts} new</span>
                          <span className="text-[var(--muted)]">,</span>
                          <span className="text-neutral-400">{r.duplicates} dupes</span>
                        </>
                      )}
                    </div>
                  ))}
                  {isCollecting && (
                    <div className="flex items-center gap-2 text-[var(--muted)]">
                      <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-blue-500" />
                      <span className="w-5 text-right">{collectResults.length + 1}.</span>
                      <span>r/{collectProgress?.subreddit || "..."}</span>
                      <span className="animate-pulse">collecting...</span>
                    </div>
                  )}
                </div>
              )}

              {/* Final summary cards */}
              {collectProgress?.done && (
                <div className="grid grid-cols-3 gap-3 pt-1">
                  <MetricCard label="Total Collected" value={String(collectProgress.total_collected ?? 0)} />
                  <MetricCard label="New Posts" value={String(collectProgress.new_posts ?? 0)} positive />
                  <MetricCard label="Duplicates" value={String(collectProgress.duplicates ?? 0)} />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PostRow({
  post,
  analyzing,
  approving,
  expanded,
  onToggleExpand,
  onAnalyze,
  onApprove,
}: {
  post: RawPost;
  analyzing: boolean;
  approving: boolean;
  expanded: boolean;
  onToggleExpand: () => void;
  onAnalyze: () => void;
  onApprove: () => void;
}) {
  const isAnalyzed = !!post.ai_processed;
  const hasStrategy = !!post.strategy_name;
  const isActionable = post.strategy_category === "ACTIONABLE_STRATEGY";

  return (
    <>
      <tr
        className={`border-b border-[var(--border)]/30 hover:bg-[var(--border)]/20 ${
          hasStrategy ? "cursor-pointer" : ""
        }`}
        onClick={hasStrategy ? onToggleExpand : undefined}
      >
        <td className="px-3 py-2">
          <StatusDot analyzed={isAnalyzed} />
        </td>
        <td className="max-w-xs truncate px-3 py-2">
          <div className="flex items-center gap-1.5">
            {hasStrategy && (
              <span className="text-[var(--muted)] text-xs">{expanded ? "▼" : "▶"}</span>
            )}
            {post.url ? (
              <a
                href={post.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[var(--primary)] hover:underline"
                title={post.title || ""}
                onClick={(e) => e.stopPropagation()}
              >
                {post.title || "Untitled"}
              </a>
            ) : (
              <span>{post.title || "Untitled"}</span>
            )}
          </div>
        </td>
        <td className="px-3 py-2 text-xs text-[var(--muted)]">
          r/{post.subreddit}
        </td>
        <td className="px-3 py-2 text-right tabular-nums">{post.score}</td>
        <td className="px-3 py-2">
          <CategoryBadge category={post.stage1_category} />
        </td>
        <td className="px-3 py-2">
          {hasStrategy ? (
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-[var(--foreground)] truncate max-w-[150px]">
                {post.strategy_name}
              </span>
              {post.ai_score != null && post.ai_score > 0 && (
                <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                  post.ai_score >= 70 ? "bg-green-500/20 text-green-400"
                  : post.ai_score >= 40 ? "bg-yellow-500/20 text-yellow-400"
                  : "bg-neutral-500/20 text-neutral-400"
                }`}>
                  {Math.round(post.ai_score)}
                </span>
              )}
              {post.rule_quality && (
                <span
                  className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                    post.rule_quality === "strong"
                      ? "bg-green-600/20 text-green-300"
                      : post.rule_quality === "medium"
                      ? "bg-yellow-600/20 text-yellow-300"
                      : "bg-neutral-500/20 text-neutral-300"
                  }`}
                  title="Rule clarity"
                >
                  {post.rule_quality}
                </span>
              )}
            </div>
          ) : (
            <span className="text-xs text-[var(--muted)]">--</span>
          )}
        </td>
        <td className="max-w-xs px-3 py-2 text-xs text-[var(--muted)]">
          {post.entry_rules?.trim() ? (
            <span className="line-clamp-2 text-[var(--foreground)]">{post.entry_rules}</span>
          ) : (
            "-"
          )}
        </td>
        <td className="max-w-xs px-3 py-2 text-xs text-[var(--muted)]">
          {post.exit_rules?.trim() ? (
            <span className="line-clamp-2 text-[var(--foreground)]">{post.exit_rules}</span>
          ) : (
            "-"
          )}
        </td>
        <td className="px-3 py-2">
          {post.strategy_id ? (
            <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
              <span className="rounded bg-neutral-600/20 px-1.5 py-0.5 text-neutral-300">
                {post.approval_status || post.strategy_status || "-"}
              </span>
              {post.execution_status && (
                <span className="rounded bg-blue-600/20 px-1.5 py-0.5 text-blue-300">
                  {post.execution_status}
                </span>
              )}
              {post.fix_category && post.fix_category !== "none" && (
                <span className="rounded bg-red-600/20 px-1.5 py-0.5 text-red-300">
                  {post.fix_category}
                </span>
              )}
            </div>
          ) : (
            <span className="text-xs text-[var(--muted)]">-</span>
          )}
        </td>
        <td className="px-3 py-2 text-right">
          {isActionable && post.strategy_id && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onApprove();
              }}
              disabled={approving}
              className="mr-2 rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-medium transition-colors hover:border-green-500 hover:text-green-400 disabled:opacity-40"
              title="Approve actionable strategy"
            >
              {approving ? "..." : "Approve"}
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onAnalyze(); }}
            disabled={analyzing}
            className="rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-medium transition-colors hover:border-[var(--primary)] hover:text-[var(--primary)] disabled:opacity-40"
          >
            {analyzing ? "..." : isAnalyzed ? "Re-analyze" : "Analyze"}
          </button>
        </td>
      </tr>
      {/* Expandable strategy detail row */}
      {expanded && hasStrategy && (
        <tr className="border-b border-[var(--border)]/30 bg-[var(--background)]">
          <td colSpan={10} className="px-6 py-3">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 text-xs">
              {post.strategy_summary && (
                <div className="md:col-span-2">
                  <span className="text-[var(--muted)]">Summary: </span>
                  <span>{post.strategy_summary}</span>
                </div>
              )}
              {post.entry_rules && (
                <div>
                  <span className="text-green-400 font-medium">Entry: </span>
                  <span className="text-[var(--foreground)]">{post.entry_rules}</span>
                </div>
              )}
              {post.exit_rules && (
                <div>
                  <span className="text-red-400 font-medium">Exit: </span>
                  <span className="text-[var(--foreground)]">{post.exit_rules}</span>
                </div>
              )}
              <div className="flex gap-4 flex-wrap">
                {post.strategy_indicators && post.strategy_indicators.length > 0 && (
                  <div>
                    <span className="text-[var(--muted)]">Indicators: </span>
                    {post.strategy_indicators.map((ind, i) => (
                      <span key={i} className="inline-block mr-1 rounded bg-blue-500/15 px-1.5 py-0.5 text-blue-400">
                        {ind}
                      </span>
                    ))}
                  </div>
                )}
                {post.tp_pct != null && (
                  <span>
                    <span className="text-[var(--muted)]">TP: </span>
                    <span className="text-green-400">{post.tp_pct}%</span>
                  </span>
                )}
                {post.sl_pct != null && (
                  <span>
                    <span className="text-[var(--muted)]">SL: </span>
                    <span className="text-red-400">{post.sl_pct}%</span>
                  </span>
                )}
                {post.strategy_timeframe && (
                  <span>
                    <span className="text-[var(--muted)]">TF: </span>
                    <span>{post.strategy_timeframe}</span>
                  </span>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
