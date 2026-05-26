"use client";

import { useEffect, useRef, useMemo } from "react";
import { createChart, type IChartApi, type UTCTimestamp } from "lightweight-charts";

interface EquityChartProps {
  data: { datetime: string; value: number }[];
  buyHoldData?: { datetime: string; value: number }[];
  height?: number;
}

function toChartData(raw: { datetime: string; value: number }[]) {
  const seen = new Map<number, number>();
  for (const d of raw) {
    const ts = Math.floor(new Date(d.datetime).getTime() / 1000);
    seen.set(ts, d.value);
  }
  return Array.from(seen.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([time, value]) => ({ time: time as UTCTimestamp, value }));
}

export function EquityChart({ data, buyHoldData, height = 350 }: EquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const chartData = useMemo(() => toChartData(data), [data]);
  const bhChartData = useMemo(
    () => (buyHoldData ? toChartData(buyHoldData) : []),
    [buyHoldData]
  );

  useEffect(() => {
    if (!containerRef.current || chartData.length === 0) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { color: "#141414" },
        textColor: "#ededed",
      },
      grid: {
        vertLines: { color: "#1e1e1e" },
        horzLines: { color: "#1e1e1e" },
      },
      timeScale: {
        borderColor: "#262626",
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: { borderColor: "#262626" },
    });
    chartRef.current = chart;

    const equitySeries = chart.addLineSeries({
      color: "#3b82f6",
      lineWidth: 2,
      title: "Strategy",
    });
    equitySeries.setData(chartData);

    if (bhChartData.length > 0) {
      const bhSeries = chart.addLineSeries({
        color: "#737373",
        lineWidth: 1,
        lineStyle: 2,
        title: "Buy & Hold",
      });
      bhSeries.setData(bhChartData);
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [chartData, bhChartData, height]);

  return <div ref={containerRef} className="w-full rounded-lg" />;
}
