"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { converterApi } from "@/lib/api";

export default function ConverterPage() {
  const [pineCode, setPineCode] = useState("");
  const [direction, setDirection] = useState("pine_to_python");

  const mutation = useMutation({ mutationFn: converterApi.convert });

  const handleConvert = () => {
    if (!pineCode.trim()) return;
    mutation.mutate({ code: pineCode, direction });
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Pine Script Converter</h1>

      <div className="flex gap-2">
        <button
          onClick={() => setDirection("pine_to_python")}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${
            direction === "pine_to_python"
              ? "bg-[var(--primary)] text-white"
              : "border border-[var(--border)] text-[var(--muted)]"
          }`}
        >
          Pine → Python
        </button>
        <button
          onClick={() => setDirection("python_to_pine")}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${
            direction === "python_to_pine"
              ? "bg-[var(--primary)] text-white"
              : "border border-[var(--border)] text-[var(--muted)]"
          }`}
        >
          Python → Pine
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-medium">
            {direction === "pine_to_python" ? "Pine Script" : "Python Code"}
          </label>
          <textarea
            value={pineCode}
            onChange={(e) => setPineCode(e.target.value)}
            rows={20}
            placeholder="Paste your code here..."
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 font-mono text-sm"
          />
          <button
            onClick={handleConvert}
            disabled={mutation.isPending || !pineCode.trim()}
            className="rounded-lg bg-[var(--primary)] px-6 py-2 font-medium text-white disabled:opacity-50"
          >
            {mutation.isPending ? "Converting..." : "Convert"}
          </button>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">
            {direction === "pine_to_python" ? "Python Output" : "Pine Script Output"}
          </label>
          <textarea
            value={mutation.data?.converted_code || ""}
            readOnly
            rows={20}
            placeholder="Converted code will appear here..."
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 font-mono text-sm"
          />
          {mutation.data && (
            <div className="flex gap-4 text-xs text-[var(--muted)]">
              <span>Model: {mutation.data.model_used}</span>
              <span>Tokens: {mutation.data.tokens_used}</span>
              <span>Cost: ${mutation.data.cost_usd.toFixed(4)}</span>
              <span className={mutation.data.is_valid ? "text-[var(--success)]" : "text-[var(--danger)]"}>
                {mutation.data.is_valid ? "Valid" : "Invalid"}
              </span>
            </div>
          )}
        </div>
      </div>

      {mutation.isError && (
        <div className="rounded-lg border border-[var(--danger)] bg-red-950/30 p-4 text-sm text-[var(--danger)]">
          {mutation.error.message}
        </div>
      )}
    </div>
  );
}
