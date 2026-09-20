import { useMemo, useState } from "react";
import { useModelEvaluationDetail, useModelEvaluationSummary } from "../../lib/queries";
import type { TickerEvaluation } from "../../lib/analyticsApi";
import { StatTile } from "../StatTile";
import { QueryState } from "../QueryState";
import { ActualVsPredictedChart } from "./ActualVsPredictedChart";
import { SectionEyebrow } from "./SectionEyebrow";

const STATUS_LABEL: Record<TickerEvaluation["status"], string> = {
  ok: "Evaluated",
  insufficient_data: "Insufficient data",
  model_unavailable: "No model",
  model_load_error: "Load error",
};

const STATUS_TONE: Record<TickerEvaluation["status"], string> = {
  ok: "bg-up-soft text-up",
  insufficient_data: "bg-surface-alt text-ink-muted",
  model_unavailable: "bg-surface-alt text-ink-muted",
  model_load_error: "bg-down-soft text-down",
};

function fmtPct(value: number | null | undefined, decimals = 1): string {
  return value == null ? "—" : `${value.toFixed(decimals)}%`;
}

function fmtNum(value: number | null | undefined, decimals = 4): string {
  return value == null ? "—" : value.toFixed(decimals);
}

function fmtPeriod(period: TickerEvaluation["test_period"]): string {
  if (!period || !period.start || !period.end) return "—";
  return `${period.start} → ${period.end} (${period.rows} obs.)`;
}

export function ModelEvaluationPanel() {
  const summary = useModelEvaluationSummary();
  const [selected, setSelected] = useState<string | null>(null);

  const okTickers = useMemo(
    () => (summary.data?.tickers ?? []).filter((t) => t.status === "ok"),
    [summary.data],
  );
  const activeTicker = selected ?? okTickers[0]?.ticker ?? null;
  const detail = useModelEvaluationDetail(activeTicker ?? "");

  const headline = okTickers.find((t) => t.ticker === activeTicker);

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-md border border-line p-4">
        <SectionEyebrow>Model Evaluation</SectionEyebrow>
        <div className="mb-1 mt-1 text-sm font-bold text-ink">Out-of-sample LSTM accuracy</div>
        <p className="text-xs text-ink-faint">
          Out-of-sample accuracy of the 12 per-ticker LSTM models, evaluated by running each
          already-trained model forward over a chronological 70% / 15% / 15% train / validation /
          test split — no model is retrained to produce this page. Metrics reflect the model's raw
          22-day-return prediction, not trading performance.
        </p>
      </div>

      <QueryState
        isLoading={summary.isLoading}
        isError={summary.isError}
        error={summary.error}
        isEmpty={(summary.data?.tickers ?? []).length === 0}
        emptyMessage="No evaluation data available."
        onRetry={() => summary.refetch()}
      >
        <div>
          <SectionEyebrow>ETF selector</SectionEyebrow>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(summary.data?.tickers ?? []).map((t) => (
              <button
                key={t.ticker}
                type="button"
                disabled={t.status !== "ok"}
                onClick={() => setSelected(t.ticker)}
                className={`rounded px-2.5 py-1 text-xs font-mono font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${
                  t.ticker === activeTicker
                    ? "bg-ink-strong text-white"
                    : "border border-line-strong text-ink-muted hover:bg-surface-alt hover:text-ink"
                }`}
              >
                {t.ticker}
              </button>
            ))}
          </div>
        </div>

        {headline && (
          <div>
            <SectionEyebrow>KPIs — {headline.ticker}</SectionEyebrow>
            <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
              <StatTile label="Test MAE" value={fmtNum(headline.test_metrics?.mae)} />
              <StatTile label="Test RMSE" value={fmtNum(headline.test_metrics?.rmse)} />
              <StatTile
                label="Directional Accuracy"
                value={fmtPct(headline.test_metrics?.directional_accuracy)}
              />
              <StatTile
                label="Test MAPE"
                value={
                  headline.test_metrics?.mape != null
                    ? fmtPct(headline.test_metrics.mape)
                    : "n/a (returns too small)"
                }
              />
            </div>
          </div>
        )}

        {activeTicker && (
          <div className="flex flex-col gap-6">
            <QueryState
              isLoading={detail.isLoading}
              isError={detail.isError}
              error={detail.error}
              isEmpty={!detail.data}
              emptyMessage="No detail available for this ticker."
            >
              {detail.data && (
                <>
                  <SectionEyebrow>Actual vs. Predicted</SectionEyebrow>
                  <div className="grid gap-6 lg:grid-cols-2">
                    <div className="rounded-md border border-line">
                      <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                        {activeTicker} — Validation: actual vs. predicted 22-day return
                      </div>
                      <div className="p-2">
                        <ActualVsPredictedChart
                          series={
                            detail.data.evaluation.validation_series ?? { dates: [], actual: [], predicted: [] }
                          }
                        />
                      </div>
                      <div className="border-t border-line px-4 py-2 text-xs text-ink-faint">
                        {fmtPeriod(detail.data.evaluation.validation_period)}
                      </div>
                    </div>
                    <div className="rounded-md border border-line">
                      <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
                        {activeTicker} — Test: actual vs. predicted 22-day return
                      </div>
                      <div className="p-2">
                        <ActualVsPredictedChart
                          series={detail.data.evaluation.test_series ?? { dates: [], actual: [], predicted: [] }}
                        />
                      </div>
                      <div className="border-t border-line px-4 py-2 text-xs text-ink-faint">
                        {fmtPeriod(detail.data.evaluation.test_period)}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </QueryState>
          </div>
        )}

        <div>
          <SectionEyebrow>Model performance by ETF</SectionEyebrow>
          <div className="mt-2 rounded-md border border-line">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                    <th className="px-4 py-2 font-semibold">Ticker</th>
                    <th className="px-4 py-2 font-semibold">Status</th>
                    <th className="px-4 py-2 font-semibold">MAE</th>
                    <th className="px-4 py-2 font-semibold">RMSE</th>
                    <th className="px-4 py-2 font-semibold">MAPE</th>
                    <th className="px-4 py-2 font-semibold">Directional Acc.</th>
                    <th className="px-4 py-2 font-semibold">Test Period</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line-soft font-mono">
                  {(summary.data?.tickers ?? []).map((t) => (
                    <tr
                      key={t.ticker}
                      onClick={() => t.status === "ok" && setSelected(t.ticker)}
                      className={`${t.status === "ok" ? "cursor-pointer hover:bg-surface-alt" : "opacity-60"} ${
                        t.ticker === activeTicker ? "bg-accent-soft" : ""
                      }`}
                    >
                      <td className="px-4 py-2.5 font-sans font-semibold text-ink">{t.ticker}</td>
                      <td className="px-4 py-2.5 font-sans">
                        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_TONE[t.status]}`}>
                          {STATUS_LABEL[t.status]}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">{fmtNum(t.test_metrics?.mae)}</td>
                      <td className="px-4 py-2.5">{fmtNum(t.test_metrics?.rmse)}</td>
                      <td className="px-4 py-2.5">
                        {t.test_metrics?.mape != null ? fmtPct(t.test_metrics.mape) : "n/a"}
                      </td>
                      <td className="px-4 py-2.5">{fmtPct(t.test_metrics?.directional_accuracy)}</td>
                      <td className="px-4 py-2.5 font-sans text-xs text-ink-muted">{fmtPeriod(t.test_period)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {activeTicker && detail.data && (
          <div>
            <SectionEyebrow>Train / Validation / Test period</SectionEyebrow>
            <div className="mt-2 grid gap-3 sm:grid-cols-3">
              <div className="rounded-md border border-line p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Train</div>
                <p className="mt-1 font-mono text-xs text-ink-muted">{fmtPeriod(detail.data.evaluation.train_period)}</p>
              </div>
              <div className="rounded-md border border-line p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Validation</div>
                <p className="mt-1 font-mono text-xs text-ink-muted">{fmtPeriod(detail.data.evaluation.validation_period)}</p>
              </div>
              <div className="rounded-md border border-line p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Test</div>
                <p className="mt-1 font-mono text-xs text-ink-muted">{fmtPeriod(detail.data.evaluation.test_period)}</p>
              </div>
            </div>
            <p className="mt-2 text-xs text-ink-faint">
              Epoch-level training/validation loss curves are not available — see methodology below.
            </p>
          </div>
        )}

        <details className="mt-6 rounded-md border border-line p-4 text-sm">
          <summary className="cursor-pointer font-bold text-ink">Methodology &amp; limitations</summary>
          <ul className="mt-3 flex flex-col gap-2 text-xs text-ink-muted">
            {(summary.data?.methodology_notes ?? []).map((note, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-ink-faint">•</span>
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </details>
      </QueryState>
    </div>
  );
}
