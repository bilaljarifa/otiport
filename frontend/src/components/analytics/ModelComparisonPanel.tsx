import { useState } from "react";
import { useModelComparison } from "../../lib/queries";
import { ETF_UNIVERSE } from "../../lib/catalog";
import { StatTile } from "../StatTile";
import { QueryState } from "../QueryState";
import { SectionEyebrow } from "./SectionEyebrow";
import type { ComparisonModelResult } from "../../lib/analyticsApi";

const TRAINED_TICKERS = ETF_UNIVERSE.filter((e) => e.hasModel).map((e) => e.ticker);

function fmt(value: number | null, decimals = 4): string {
  return value == null ? "--" : value.toFixed(decimals);
}

function fmtPct(value: number | null): string {
  return value == null ? "--" : `${value.toFixed(1)}%`;
}

/** Lower is better for MAE/RMSE, higher is better for directional accuracy —
 * only picks a "best" among models that actually produced that metric
 * (status "ok" and a non-null value), never among placeholders. */
function bestBy(
  models: ComparisonModelResult[],
  key: "mae" | "rmse" | "directional_accuracy",
  higherIsBetter: boolean,
): ComparisonModelResult | null {
  const candidates = models.filter((m) => m.status === "ok" && m[key] != null);
  if (candidates.length === 0) return null;
  return candidates.reduce((best, m) =>
    (higherIsBetter ? m[key]! > best[key]! : m[key]! < best[key]!) ? m : best,
  );
}

/**
 * Benchmarks the existing LSTM against transparent, non-ML baselines
 * (naive/last-value, moving average, linear regression) over the identical
 * chronological test split `backend/model_evaluation.py` already evaluates
 * the LSTM against (`backend/model_comparison.py` reuses that split and
 * metrics function directly — not a second methodology). Never declares an
 * overall "winner": each headline names the specific metric it's based on.
 */
export function ModelComparisonPanel() {
  const [ticker, setTicker] = useState(TRAINED_TICKERS[0] ?? "PSI");
  const comparison = useModelComparison(ticker);
  const data = comparison.data;

  const bestMae = data ? bestBy(data.models, "mae", false) : null;
  const bestRmse = data ? bestBy(data.models, "rmse", false) : null;
  const bestDirectional = data ? bestBy(data.models, "directional_accuracy", true) : null;

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-md border border-line p-4">
        <SectionEyebrow>Model Comparison</SectionEyebrow>
        <div className="mb-1 mt-1 text-sm font-bold text-ink">
          Benchmark the LSTM against simpler forecasting approaches
        </div>
        <p className="mb-3 text-xs text-ink-faint">
          Naive/last-value, a moving average, and a plain linear regression, all evaluated over the
          exact same chronological test period and 22-day forward-return target the LSTM is already
          evaluated with — never a second, incompatible methodology.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {TRAINED_TICKERS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTicker(t)}
              className={`rounded px-2.5 py-1 text-xs font-mono font-semibold ${
                ticker === t
                  ? "bg-ink-strong text-white"
                  : "border border-line-strong text-ink-muted hover:bg-surface-alt hover:text-ink"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <QueryState
        isLoading={comparison.isLoading}
        isError={comparison.isError}
        error={comparison.error}
        onRetry={() => void comparison.refetch()}
      >
        {data && data.status !== "ok" && (
          <div className="rounded-md border border-dashed border-line px-6 py-10 text-center text-sm text-ink-muted">
            {data.detail ?? "Insufficient data for this comparison."}
          </div>
        )}

        {data && data.status === "ok" && (
          <>
            <SectionEyebrow>Key Results</SectionEyebrow>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <StatTile label="Lowest MAE" value={bestMae ? bestMae.label : "--"} hint={bestMae ? fmt(bestMae.mae) : undefined} />
              <StatTile label="Lowest RMSE" value={bestRmse ? bestRmse.label : "--"} hint={bestRmse ? fmt(bestRmse.rmse) : undefined} />
              <StatTile
                label="Highest Directional Accuracy"
                value={bestDirectional ? bestDirectional.label : "--"}
                hint={bestDirectional ? fmtPct(bestDirectional.directional_accuracy) : undefined}
              />
            </div>
            <p className="text-xs text-ink-faint">
              Each headline names the specific metric it's measured on — no single model is declared
              an overall winner.
            </p>

            <SectionEyebrow>Performance Table</SectionEyebrow>
            <div className="rounded-md border border-line">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                      <th className="px-4 py-2 font-semibold">Model</th>
                      <th className="px-4 py-2 font-semibold">MAE</th>
                      <th className="px-4 py-2 font-semibold">RMSE</th>
                      <th className="px-4 py-2 font-semibold">Directional Accuracy</th>
                      <th className="px-4 py-2 font-semibold">Observations</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line-soft font-mono">
                    {data.models.map((m) => (
                      <tr key={m.model} className={m.model === "lstm" ? "bg-accent-soft" : ""}>
                        <td className="px-4 py-2.5 font-sans font-semibold text-ink">
                          {m.label}
                          {m.status !== "ok" && (
                            <span className="ml-2 font-sans text-xs font-normal text-ink-faint">
                              ({m.detail ?? m.status})
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2.5">{fmt(m.mae)}</td>
                        <td className="px-4 py-2.5">{fmt(m.rmse)}</td>
                        <td className="px-4 py-2.5">{fmtPct(m.directional_accuracy)}</td>
                        <td className="px-4 py-2.5">{m.observations || "--"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {data.test_period && data.methodology && (
              <>
                <SectionEyebrow>Methodology</SectionEyebrow>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <StatTile label="Test Period" value={`${data.test_period.start} → ${data.test_period.end}`} />
                  <StatTile label="Observations" value={String(data.test_period.observations)} />
                  <StatTile label="Forecast Horizon" value={`${data.methodology.forecast_horizon_days}d`} />
                  <StatTile label="Target" value="return_22d" hint="22-day forward return" />
                </div>
              </>
            )}

            <details className="rounded-md border border-line p-4 text-sm">
              <summary className="cursor-pointer font-bold text-ink">Limitations</summary>
              <ul className="mt-3 flex flex-col gap-2 text-xs text-ink-muted">
                <li className="flex gap-2">
                  <span className="text-ink-faint">•</span>
                  <span>
                    Naive predicts the previous 22-day return; moving average predicts the trailing
                    10-observation mean; linear regression is fit once on the chronological training
                    split only. None use the sequence structure the LSTM does.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-ink-faint">•</span>
                  <span>
                    All four models are evaluated on the identical test-split target dates — a fair,
                    like-for-like comparison, not four different samples.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-ink-faint">•</span>
                  <span>Historical test performance does not guarantee future forecasting performance for any model shown here.</span>
                </li>
              </ul>
            </details>
          </>
        )}
      </QueryState>
    </div>
  );
}
