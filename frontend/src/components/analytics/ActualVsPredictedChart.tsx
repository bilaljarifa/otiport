import { useEffect, useRef } from "react";
import { createChart, LineSeries, ColorType, type Time } from "lightweight-charts";
import type { ActualPredictedSeries } from "../../lib/analyticsApi";
import { useTheme } from "../../theme/ThemeContext";

/**
 * Actual vs. model-predicted 22-day return for one evaluation split
 * (validation or test). Both series come straight from the backend's
 * out-of-sample run (`backend/model_evaluation.py`) — the model is never
 * re-run in the browser.
 */
export function ActualVsPredictedChart({
  series,
  height = 300,
}: {
  series: ActualPredictedSeries;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    const container = containerRef.current;
    if (!container || series.dates.length === 0) return;

    const styles = getComputedStyle(document.documentElement);
    const surface = styles.getPropertyValue("--app-bg").trim() || "#ffffff";
    const text = styles.getPropertyValue("--chart-text").trim() || "#667085";
    const grid = styles.getPropertyValue("--chart-grid").trim() || "#f1f3f5";
    const line = styles.getPropertyValue("--color-line").trim() || "#e5e5e5";

    const chart = createChart(container, {
      layout: { background: { type: ColorType.Solid, color: surface }, textColor: text },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      timeScale: { borderColor: line },
      rightPriceScale: { borderColor: line, mode: 0 },
      localization: { priceFormatter: (p: number) => `${(p * 100).toFixed(1)}%` },
      width: container.clientWidth,
      height,
    });

    const actualSeries = chart.addSeries(LineSeries, { color: "#0f1115", lineWidth: 2, title: "Actual" });
    actualSeries.setData(series.dates.map((d, i) => ({ time: d as Time, value: series.actual[i] })));

    const predictedSeries = chart.addSeries(LineSeries, {
      color: "#2563eb",
      lineWidth: 2,
      lineStyle: 2,
      title: "Predicted",
    });
    predictedSeries.setData(series.dates.map((d, i) => ({ time: d as Time, value: series.predicted[i] })));

    chart.timeScale().fitContent();

    const handleResize = () => chart.applyOptions({ width: container.clientWidth });
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [series, height, theme]);

  if (series.dates.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-ink-faint" style={{ height }}>
        No data available for this split.
      </div>
    );
  }

  return <div ref={containerRef} className="w-full" style={{ height }} />;
}
