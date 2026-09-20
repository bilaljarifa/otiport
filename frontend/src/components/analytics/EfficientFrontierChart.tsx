/**
 * Real mean-variance efficient frontier from `POST /efficient-frontier`
 * (`backend/optimizer.py::compute_efficient_frontier`) — every point is an
 * actual optimized portfolio for a target return, not an interpolated or
 * decorative curve. Plain SVG, matching the other analytics-panel charts
 * (`../newsAnalytics/Charts.tsx`) rather than pulling in a second charting
 * library just for one frontier line.
 */

const VIEW_WIDTH = 600;
const VIEW_HEIGHT = 280;
const PAD_LEFT = 44;
const PAD_BOTTOM = 28;
const PAD_TOP = 12;
const PAD_RIGHT = 16;

export interface FrontierPoint {
  volatility: number;
  return: number;
}

export function EfficientFrontierChart({
  points,
  maxSharpe,
  minVolatility,
  selected,
}: {
  points: FrontierPoint[];
  maxSharpe?: FrontierPoint;
  minVolatility?: FrontierPoint;
  selected?: FrontierPoint;
}) {
  if (points.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center text-sm text-ink-faint">
        No frontier data to chart.
      </div>
    );
  }

  const allX = points.map((p) => p.volatility).concat(selected ? [selected.volatility] : []);
  const allY = points.map((p) => p.return).concat(selected ? [selected.return] : []);
  const xMin = Math.min(...allX);
  const xMax = Math.max(...allX);
  const yMin = Math.min(...allY);
  const yMax = Math.max(...allY);
  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;

  const toSvgX = (v: number) => PAD_LEFT + ((v - xMin) / xSpan) * (VIEW_WIDTH - PAD_LEFT - PAD_RIGHT);
  const toSvgY = (r: number) =>
    VIEW_HEIGHT - PAD_BOTTOM - ((r - yMin) / ySpan) * (VIEW_HEIGHT - PAD_TOP - PAD_BOTTOM);

  const sorted = [...points].sort((a, b) => a.volatility - b.volatility);
  const path = sorted.map((p, i) => `${i === 0 ? "M" : "L"} ${toSvgX(p.volatility)} ${toSvgY(p.return)}`).join(" ");

  const yTicks = 4;
  const xTicks = 4;

  return (
    <svg viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`} className="w-full" style={{ height: VIEW_HEIGHT }}>
      {Array.from({ length: yTicks + 1 }, (_, i) => {
        const r = yMin + (ySpan * i) / yTicks;
        const y = toSvgY(r);
        return (
          <g key={`y-${i}`}>
            <line x1={PAD_LEFT} y1={y} x2={VIEW_WIDTH - PAD_RIGHT} y2={y} className="stroke-line-soft" strokeWidth={1} />
            <text x={4} y={y + 3} className="fill-ink-faint" fontSize={9}>
              {(r * 100).toFixed(0)}%
            </text>
          </g>
        );
      })}
      {Array.from({ length: xTicks + 1 }, (_, i) => {
        const v = xMin + (xSpan * i) / xTicks;
        const x = toSvgX(v);
        return (
          <g key={`x-${i}`}>
            <text x={x} y={VIEW_HEIGHT - 10} textAnchor="middle" className="fill-ink-faint" fontSize={9}>
              {(v * 100).toFixed(0)}%
            </text>
          </g>
        );
      })}
      <text x={PAD_LEFT} y={VIEW_HEIGHT - 2} className="fill-ink-faint" fontSize={9}>
        Volatility →
      </text>

      <path d={path} fill="none" className="stroke-accent" strokeWidth={2} />

      {minVolatility && (
        <circle cx={toSvgX(minVolatility.volatility)} cy={toSvgY(minVolatility.return)} r={4} className="fill-up">
          <title>Min volatility portfolio</title>
        </circle>
      )}
      {maxSharpe && (
        <circle cx={toSvgX(maxSharpe.volatility)} cy={toSvgY(maxSharpe.return)} r={4} className="fill-ink-strong">
          <title>Max Sharpe portfolio</title>
        </circle>
      )}
      {selected && (
        <circle
          cx={toSvgX(selected.volatility)}
          cy={toSvgY(selected.return)}
          r={6}
          className="fill-down"
          stroke="white"
          strokeWidth={1.5}
        >
          <title>Selected strategy</title>
        </circle>
      )}
    </svg>
  );
}
