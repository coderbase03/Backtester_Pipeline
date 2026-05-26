"use client";

export default function OptimizePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Parameter Optimization</h1>
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-8 text-center">
        <p className="text-lg text-[var(--muted)]">
          Grid search and Bayesian optimization for strategy parameters.
        </p>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Select a strategy, define parameter ranges, and find the optimal configuration.
        </p>
      </div>
    </div>
  );
}
