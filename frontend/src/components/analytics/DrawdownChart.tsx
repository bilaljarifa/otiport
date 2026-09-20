import { useEffect, useRef } from "react";
import { createChart, AreaSeries, ColorType, type Time } from "lightweight-charts";
import { useTheme } from "../../theme/ThemeContext";

export interface DrawdownPoint {
  date: string;
  drawdown_pct: number;
}

/**
 * Underwater equity curve — how far below its own running peak the
 * strategy's equity was on each day, computed client-side from the real
 * `equity_curve` a completed backtest already returned (`peak - equity) /
 * peak`, a standard derived statistic, never a separately fabricated
 * series). Mirrors `EquityCurveChart`'s own theming/resize setup exactly.
 */
export function DrawdownChart({ points, height = 200 }: { points: DrawdownPoint[]; height?: number }) {
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
      localization: { priceFormatter: (p: number) => `${p.toFixed(1)}%` },
      width: container.clientWidth,
      height,
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: "#dc2626",
      topColor: "rgba(220, 38, 38, 0.28)",
      bottomColor: "rgba(220, 38, 38, 0.02)",
      lineWidth: 2,
      title: "Drawdown",
    });
    series.setData(points.map((p) => ({ time: p.date as Time, value: p.drawdown_pct })));

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
        No drawdown data to display.
      </div>
    );
  }

  return <div ref={containerRef} className="w-full" style={{ height }} />;
}
