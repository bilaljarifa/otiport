import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  ColorType,
  type Time,
} from "lightweight-charts";
import type { OHLCBar } from "../lib/marketApi";
import { useTheme } from "../theme/ThemeContext";

/**
 * Real OHLC candlesticks + volume, rendered with TradingView's
 * lightweight-charts. Every bar comes from `bars` (real backend data via
 * `GET /market/ohlc`) — this component draws whatever it's given and
 * fabricates nothing itself.
 */
export function CandlestickChart({ bars, height = 380 }: { bars: OHLCBar[]; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);
  // `theme` itself is unused directly below — the chart reads colors from
  // CSS custom properties, which only change when `data-theme` flips. It's
  // in the dependency array purely so toggling dark mode while this chart is
  // already mounted tears down and recreates it with the new palette,
  // instead of leaving stale (invisible-on-the-new-background) colors until
  // the next unmount/remount.
  const { theme } = useTheme();

  useEffect(() => {
    const container = containerRef.current;
    if (!container || bars.length === 0) return;

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

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#16a34a",
      downColor: "#dc2626",
      borderVisible: false,
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
    });
    candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: 0.3 } });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
      color: "#d0d0d0",
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });

    candleSeries.setData(
      bars.map((b) => ({
        time: b.time as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );
    volumeSeries.setData(
      bars.map((b) => ({
        time: b.time as Time,
        value: b.volume,
        color: b.close >= b.open ? "rgba(22, 163, 74, 0.5)" : "rgba(220, 38, 38, 0.5)",
      })),
    );
    chart.timeScale().fitContent();

    const handleResize = () => chart.applyOptions({ width: container.clientWidth });
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [bars, height, theme]);

  if (bars.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-sm text-ink-faint"
        style={{ height }}
      >
        No chart data available for this ticker.
      </div>
    );
  }

  return <div ref={containerRef} className="w-full" style={{ height }} />;
}
