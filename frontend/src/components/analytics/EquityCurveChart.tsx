import { useEffect, useRef } from "react";
import { createChart, LineSeries, ColorType, type Time } from "lightweight-charts";
import type { EquityPoint } from "../../lib/analyticsApi";
import { useTheme } from "../../theme/ThemeContext";

/**
 * Strategy vs. benchmark equity curve for the backtest result. Every point
 * comes from the backend's day-by-day mark-to-market simulation
 * (`backend/backtester.py`) — nothing here is smoothed or fabricated.
 */
export function EquityCurveChart({ points, height = 340 }: { points: EquityPoint[]; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    const container = containerRef.current;
    if (!container || points.length === 0) return;

    const styles = getComputedStyle(document.documentElement);
    const surface = styles.getPropertyValue("--app-bg").trim() || "#ffffff";
    const text = styles.getPropertyValue("--chart-text").trim() || "#667085";
    const grid = styles.getPropertyValue("--chart-grid").trim() || "#f1f3f5";
    const line = styles.getPropertyValue("--color-line").trim() || "#e5e5e5";

    const chart = createChart(container, {
      layout: { background: { type: ColorType.Solid, color: surface }, textColor: text },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      timeScale: { borderColor: line },
      rightPriceScale: { borderColor: line },
      width: container.clientWidth,
      height,
    });

    const strategySeries = chart.addSeries(LineSeries, {
      color: "#2563eb",
      lineWidth: 2,
      title: "Strategy",
    });
    strategySeries.setData(
      points.map((p) => ({ time: p.date as Time, value: p.strategy_equity })),
    );

    if (points.some((p) => p.benchmark_equity != null)) {
      const benchmarkSeries = chart.addSeries(LineSeries, {
        color: "#94a3b8",
        lineWidth: 2,
        lineStyle: 2,
        title: "Benchmark",
      });
      benchmarkSeries.setData(
        points
          .filter((p) => p.benchmark_equity != null)
          .map((p) => ({ time: p.date as Time, value: p.benchmark_equity as number })),
      );
    }

    chart.timeScale().fitContent();

    const handleResize = () => chart.applyOptions({ width: container.clientWidth });
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [points, height, theme]);

  if (points.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-ink-faint" style={{ height }}>
        No equity curve to display.
      </div>
    );
  }

  return <div ref={containerRef} className="w-full" style={{ height }} />;
}
