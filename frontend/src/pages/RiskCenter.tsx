import { useState } from "react";
import { Link } from "react-router-dom";
import { usePortfolioRisk } from "../lib/queries";
import { money, percent, signedPercent } from "../lib/format";
import { StatTile } from "../components/StatTile";
import { QueryState } from "../components/QueryState";
import { FilterGroup } from "../components/FilterGroup";

const BENCHMARKS: { value: string; label: string }[] = [
  { value: "SPY", label: "SPY" },
  { value: "QQQ", label: "QQQ" },
];

function correlationTone(value: number): string {
  if (value >= 0.7) return "bg-down/20 text-down";
  if (value >= 0.3) return "bg-down/10 text-ink";
  if (value <= -0.3) return "bg-up/15 text-up";
  return "text-ink-muted";
}

export function RiskCenterPage() {
  const [benchmark, setBenchmark] = useState("SPY");
  const risk = usePortfolioRisk(benchmark);
  const data = risk.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-ink">Risk Center</h1>
          <p className="mt-1 text-xs text-ink-faint">
            Risk profile of your current holdings, using trailing 1-year historical data.
          </p>
        </div>
        <FilterGroup value={benchmark} onChange={setBenchmark} options={BENCHMARKS} />
      </div>

      <QueryState
        isLoading={risk.isLoading}
        isError={risk.isError}
        error={risk.error}
        onRetry={() => void risk.refetch()}
      >
        {data?.status === "empty" && (
          <div className="rounded-md border border-dashed border-line px-4 py-10 text-center">
            <p className="text-sm font-semibold text-ink">No open positions to analyze.</p>
            <p className="mt-1 text-sm text-ink-muted">
              Risk metrics need at least one holding.{" "}
              <Link to="/app/trading" className="font-semibold underline underline-offset-2">
                Place a trade →
              </Link>
            </p>
          </div>
        )}

        {data?.status === "ok" && (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
              <StatTile label="Volatility (ann.)" value={percent(data.volatility_pct ?? 0, 1)} />
              <StatTile label="Sharpe Ratio" value={(data.sharpe_ratio ?? 0).toFixed(2)} />
              <StatTile label="Max Drawdown" value={signedPercent(data.max_drawdown_pct ?? 0, 1)} />
              <StatTile
                label={`Beta (vs ${data.benchmark_ticker ?? "—"})`}
                value={data.beta != null ? data.beta.toFixed(2) : "—"}
              />
              <StatTile
                label="VaR (95%, 1-day)"
                value={data.var ? money(data.var.var_dollar, 0) : "—"}
                hint={data.var ? percent(Math.abs(data.var.var_pct), 2) : undefined}
              />
              <StatTile
                label="Diversification"
                value={data.diversification_score != null ? data.diversification_score.toFixed(2) : "—"}
              />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <div className="rounded-md border border-line">
                <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                  Risk contribution by position
                </div>
                <div className="flex flex-col gap-3 p-4">
                  {data.positions.map((p) => (
                    <div key={p.ticker} className="flex flex-col gap-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono font-semibold text-ink">{p.ticker}</span>
                        <span className="text-ink-muted">
                          {percent(p.risk_contribution_pct, 1)} of risk · {percent(p.weight_pct, 1)} of value
                        </span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-surface-alt">
                        <div
                          className="h-full rounded-full bg-accent-strong"
                          style={{ width: `${Math.min(Math.max(p.risk_contribution_pct, 0), 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-md border border-line p-4">
                <div className="mb-3 text-sm font-bold text-ink">Exposure by region</div>
                <div className="flex flex-col gap-2">
                  {data.exposure_by_region.map((r) => (
                    <div key={r.region} className="flex flex-col gap-1">
                      <div className="flex items-center justify-between text-xs text-ink-muted">
                        <span>{r.region}</span>
                        <span className="font-mono">{percent(r.weight_pct, 1)}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-surface-alt">
                        <div
                          className="h-full rounded-full bg-ink-strong"
                          style={{ width: `${Math.min(r.weight_pct, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 flex items-center justify-between border-t border-line-soft pt-3 text-xs">
                  <span className="text-ink-muted">Cash</span>
                  <span className="font-mono font-semibold text-ink">
                    {money(data.cash, 0)} ({percent(data.cash_pct, 1)})
                  </span>
                </div>
              </div>
            </div>

            {data.correlation_matrix && (
              <div className="rounded-md border border-line">
                <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                  Correlation matrix
                </div>
                <div className="overflow-x-auto p-2">
                  <table className="min-w-[420px] border-collapse text-xs">
                    <thead>
                      <tr>
                        <th className="px-2 py-1.5" />
                        {data.correlation_matrix.tickers.map((t) => (
                          <th key={t} className="px-2 py-1.5 text-center font-mono font-semibold text-ink-faint">
                            {t}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.correlation_matrix.values.map((row, i) => (
                        <tr key={data.correlation_matrix!.tickers[i]}>
                          <td className="px-2 py-1.5 font-mono font-semibold text-ink-faint">
                            {data.correlation_matrix!.tickers[i]}
                          </td>
                          {row.map((v, j) => (
                            <td
                              key={j}
                              className={`px-2 py-1.5 text-center font-mono ${correlationTone(v)}`}
                            >
                              {v.toFixed(2)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <details className="rounded-md border border-line p-4 text-sm">
              <summary className="cursor-pointer font-bold text-ink">Methodology &amp; limitations</summary>
              <ul className="mt-3 flex flex-col gap-2 text-xs text-ink-muted">
                {data.methodology_notes.map((note, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-ink-faint">•</span>
                    <span>{note}</span>
                  </li>
                ))}
              </ul>
            </details>
          </>
        )}
      </QueryState>
    </div>
  );
}
