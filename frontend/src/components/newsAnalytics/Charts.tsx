/**
 * Small, dependency-free SVG chart primitives for News Impact Analytics.
 *
 * `lightweight-charts` (used elsewhere for OHLC/equity curves) requires
 * daily "yyyy-mm-dd" or UNIX-timestamp time values with strictly ascending,
 * de-duplicated points — a poor fit for the 24H range's hourly buckets and
 * for a plain sentiment-vs-return scatter. These stay intentionally simple:
 * a responsive `viewBox` SVG, theme color tokens via `fill-*`/`stroke-*`
 * utilities (so they follow light/dark mode automatically), and no external
 * charting dependency.
 *
 * Bar sizing is density-aware: `computeBarPlacement` caps bar width at
 * `MAX_BAR_WIDTH` regardless of how few points are supplied, so 1-3 real
 * observations render as compact, evenly-spaced, intentional-looking bars
 * instead of stretching to fill the whole viewBox (the old formula divided
 * the full width by the point count, so 2 points produced two ~300px-wide
 * rectangles). No data is ever interpolated, duplicated or fabricated here —
 * these components only lay out whatever points they are given.
 */

const VIEW_WIDTH = 600;
const AXIS_LABEL_WIDTH = 34;
const CHART_LEFT = AXIS_LABEL_WIDTH;
const PLOT_WIDTH = VIEW_WIDTH - CHART_LEFT;
const MAX_BAR_WIDTH = 48;
const MIN_BAR_GAP = 6;

function niceLabel(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

/** Classifies a point count into the reusable data-density tiers used
 * across the news analytics charts: 0 = empty, 1-3 = sparse (compact
 * categorical/point rendering), 4-7 = compact time-series, 8+ = normal
 * time-series. Exported so it can be unit-tested and reused by callers
 * that need to decide on supporting copy (e.g. a "limited coverage" note). */
export type ChartDensity = "empty" | "sparse" | "compact" | "dense";

export function classifyChartDensity(count: number): ChartDensity {
  if (count <= 0) return "empty";
  if (count <= 3) return "sparse";
  if (count <= 7) return "compact";
  return "dense";
}

/** Bar width is capped at `MAX_BAR_WIDTH` and each bar is centered within
 * its evenly-spaced slot — this is what keeps sparse data compact instead
 * of stretched, while converging to the previous full-width behavior once
 * there are enough points that the natural slot width is already small. */
function computeBarPlacement(n: number): { barWidth: number; slotWidth: number } {
  const slotWidth = PLOT_WIDTH / Math.max(n, 1);
  const barWidth = Math.max(Math.min(slotWidth - MIN_BAR_GAP, MAX_BAR_WIDTH), 3);
  return { barWidth, slotWidth };
}

function barX(i: number, slotWidth: number, barWidth: number): number {
  return CHART_LEFT + i * slotWidth + (slotWidth - barWidth) / 2;
}

const AXIS_LABEL_PROPS = { fontSize: 9, className: "fill-ink-faint" } as const;

/** Bars centered on a zero baseline — positive values grow up (green),
 * negative grow down (red). Used for sentiment-over-time and impact history. */
export function DivergingBarChart({
  points,
  min = -1,
  max = 1,
  height = 140,
  formatValue = (v: number) => niceLabel(v),
}: {
  points: { label: string; value: number; count?: number; tooltip?: string }[];
  min?: number;
  max?: number;
  height?: number;
  formatValue?: (v: number) => string;
}) {
  if (points.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-ink-faint" style={{ height }}>
        No data to chart.
      </div>
    );
  }

  const density = classifyChartDensity(points.length);
  const scale = Math.max(Math.abs(min), Math.abs(max), 1e-6);
  const zeroY = height / 2;
  const { barWidth, slotWidth } = computeBarPlacement(points.length);
  const showEveryNth = Math.max(Math.ceil(points.length / 8), 1);
  const showInlineLabels = density === "sparse" || density === "compact";

  const yTicks = [max, max / 2, 0, min / 2, min];

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${VIEW_WIDTH} ${height}`} className="w-full" style={{ height }} preserveAspectRatio="none">
        {yTicks.map((tick, idx) => {
          const y = zeroY - (tick / scale) * (height / 2 - 4);
          return (
            <g key={idx}>
              <line
                x1={CHART_LEFT}
                y1={y}
                x2={VIEW_WIDTH}
                y2={y}
                className="stroke-line"
                strokeWidth={tick === 0 ? 1 : 0.5}
                opacity={tick === 0 ? 1 : 0.4}
              />
              <text x={CHART_LEFT - 4} y={y} textAnchor="end" dominantBaseline="middle" {...AXIS_LABEL_PROPS}>
                {tick > 0 ? "+" : ""}
                {niceLabel(tick, 1)}
              </text>
            </g>
          );
        })}
        {points.map((p, i) => {
          const magnitude = (Math.min(Math.abs(p.value), scale) / scale) * (height / 2 - 4);
          const x = barX(i, slotWidth, barWidth);
          const isPositive = p.value >= 0;
          const y = isPositive ? zeroY - magnitude : zeroY;
          const barHeight = Math.max(magnitude, 1);
          return (
            <g key={i}>
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={barHeight}
                className={isPositive ? "fill-up" : "fill-down"}
                opacity={0.85}
              >
                <title>{p.tooltip ?? `${p.label}: ${formatValue(p.value)}${p.count != null ? ` (${p.count} article${p.count === 1 ? "" : "s"})` : ""}`}</title>
              </rect>
              {showInlineLabels && (
                <text
                  x={x + barWidth / 2}
                  y={isPositive ? y - 5 : y + barHeight + 11}
                  textAnchor="middle"
                  fontSize={9}
                  className="fill-ink-muted"
                >
                  {formatValue(p.value)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div
        className="mt-1 flex justify-between text-[10px] text-ink-faint"
        style={{ paddingLeft: `${(CHART_LEFT / VIEW_WIDTH) * 100}%` }}
      >
        {points
          .filter((_, i) => i % showEveryNth === 0 || i === points.length - 1)
          .map((p, i) => (
            <span key={i} className="truncate">
              {p.label}
            </span>
          ))}
      </div>
    </div>
  );
}

/** Plain bars from zero — used for article volume over time. */
export function SimpleBarChart({
  points,
  height = 100,
}: {
  points: { label: string; value: number; tooltip?: string }[];
  height?: number;
}) {
  if (points.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-ink-faint" style={{ height }}>
        No data to chart.
      </div>
    );
  }

  const density = classifyChartDensity(points.length);
  const rawMax = Math.max(...points.map((p) => p.value), 1);
  // 20% headroom above the tallest bar so it never touches the top edge,
  // rounded up to a step that makes the mid/top tick labels tidy.
  const axisMax = Math.ceil(rawMax * 1.2) || 1;
  const { barWidth, slotWidth } = computeBarPlacement(points.length);
  const showEveryNth = Math.max(Math.ceil(points.length / 8), 1);
  const showInlineLabels = density === "sparse" || density === "compact";
  const plotHeight = height - 14; // leaves room for inline count labels

  const yTicks = [axisMax, axisMax / 2, 0];

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${VIEW_WIDTH} ${height}`} className="w-full" style={{ height }} preserveAspectRatio="none">
        {yTicks.map((tick, idx) => {
          const y = plotHeight - (tick / axisMax) * (plotHeight - 4);
          return (
            <g key={idx}>
              <line
                x1={CHART_LEFT}
                y1={y}
                x2={VIEW_WIDTH}
                y2={y}
                className="stroke-line"
                strokeWidth={tick === 0 ? 1 : 0.5}
                opacity={tick === 0 ? 1 : 0.4}
              />
              <text x={CHART_LEFT - 4} y={y} textAnchor="end" dominantBaseline="middle" {...AXIS_LABEL_PROPS}>
                {Math.round(tick)}
              </text>
            </g>
          );
        })}
        {points.map((p, i) => {
          const barHeight = (p.value / axisMax) * (plotHeight - 4);
          const x = barX(i, slotWidth, barWidth);
          const h = Math.max(barHeight, p.value > 0 ? 1 : 0);
          return (
            <g key={i}>
              <rect
                x={x}
                y={plotHeight - h}
                width={barWidth}
                height={h}
                className="fill-accent"
                opacity={0.85}
              >
                <title>{p.tooltip ?? `${p.label}: ${p.value} article${p.value === 1 ? "" : "s"}`}</title>
              </rect>
              {showInlineLabels && (
                <text x={x + barWidth / 2} y={plotHeight - h - 5} textAnchor="middle" fontSize={9} className="fill-ink-muted">
                  {p.value}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div
        className="mt-1 flex justify-between text-[10px] text-ink-faint"
        style={{ paddingLeft: `${(CHART_LEFT / VIEW_WIDTH) * 100}%` }}
      >
        {points
          .filter((_, i) => i % showEveryNth === 0 || i === points.length - 1)
          .map((p, i) => (
            <span key={i} className="truncate">
              {p.label}
            </span>
          ))}
      </div>
    </div>
  );
}

/** Sentiment (x) vs. daily return % (y) — one point per day with matching
 * news and price data. Deliberately unlabeled trendline-free: the
 * correlation coefficient is reported as a number alongside, never implied
 * visually by a fitted line the data may not actually support. */
export function ScatterPlot({
  points,
  height = 220,
}: {
  points: { x: number; y: number; label: string }[];
  height?: number;
}) {
  if (points.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-ink-faint" style={{ height }}>
        No data to chart.
      </div>
    );
  }

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xMax = Math.max(Math.abs(Math.min(...xs)), Math.abs(Math.max(...xs)), 0.1);
  const yMax = Math.max(Math.abs(Math.min(...ys)), Math.abs(Math.max(...ys)), 0.1);

  const pad = 16;
  const toSvgX = (x: number) => pad + ((x + xMax) / (2 * xMax)) * (VIEW_WIDTH - 2 * pad);
  const toSvgY = (y: number) => pad + ((yMax - y) / (2 * yMax)) * (height - 2 * pad);

  return (
    <svg viewBox={`0 0 ${VIEW_WIDTH} ${height}`} className="w-full" style={{ height }} preserveAspectRatio="none">
      <line x1={toSvgX(0)} y1={0} x2={toSvgX(0)} y2={height} className="stroke-line" strokeWidth={1} />
      <line x1={0} y1={toSvgY(0)} x2={VIEW_WIDTH} y2={toSvgY(0)} className="stroke-line" strokeWidth={1} />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={toSvgX(p.x)}
          cy={toSvgY(p.y)}
          r={4}
          className={p.y >= 0 ? "fill-up" : "fill-down"}
          opacity={0.8}
        >
          <title>
            {p.label}: sentiment {niceLabel(p.x)}, return {niceLabel(p.y)}%
          </title>
        </circle>
      ))}
    </svg>
  );
}
