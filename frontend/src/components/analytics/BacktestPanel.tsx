import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { startBacktestJob, getBacktestJobStatus } from "../../lib/analyticsApi";
import type { Strategy, BacktestResponse } from "../../lib/analyticsApi";
import { ApiError } from "../../lib/apiClient";
import { ETF_UNIVERSE } from "../../lib/catalog";
import { money, percent, signedPercent } from "../../lib/format";
import { StatTile } from "../StatTile";
import { Button } from "../Button";
import { FilterGroup } from "../FilterGroup";
import { EquityCurveChart } from "./EquityCurveChart";
import { DrawdownChart } from "./DrawdownChart";
import { SectionEyebrow } from "./SectionEyebrow";

const TRAINED_TICKERS = ETF_UNIVERSE.filter((e) => e.ticker !== "SPY" && e.ticker !== "QQQ");
const BENCHMARK_OPTIONS = ["SPY", "QQQ", "None"] as const;

const STRATEGIES: { value: Strategy; label: string }[] = [
  { value: "max_sharpe", label: "Max Sharpe" },
  { value: "min_volatility", label: "Min Volatility" },
  { value: "risk_parity", label: "Risk Parity" },
  { value: "equal_weight", label: "Equal Weight" },
];

type Preset = "3M" | "6M" | "1Y" | "3Y" | "custom";
const PRESETS: { value: Preset; label: string }[] = [
  { value: "3M", label: "3M" },
  { value: "6M", label: "6M" },
  { value: "1Y", label: "1Y" },
  { value: "3Y", label: "3Y" },
  { value: "custom", label: "Custom" },
];
const PRESET_MONTHS: Record<Exclude<Preset, "custom">, number> = { "3M": 3, "6M": 6, "1Y": 12, "3Y": 36 };

const PHASE_LABEL: Record<string, string> = {
  starting: "Starting…",
  loading_models: "Loading LSTM models…",
  fetching_data: "Fetching historical market data…",
  computing_features: "Computing technical features…",
  forecasting: "Running LSTM forecasts…",
  simulating: "Simulating rebalance periods…",
  done: "Finalizing…",
};

const INPUT_CLASS =
  "rounded border border-line-strong bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:ring-1 focus:ring-ink/10";

function rangeForPreset(preset: Exclude<Preset, "custom">): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - PRESET_MONTHS[preset]);
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) };
}

/** Underwater curve derived from the backtest's own real equity_curve —
 * peak-to-date minus current equity, a standard statistic computed here
 * rather than a second value the backend would have to compute and return. */
function computeDrawdown(points: BacktestResponse["equity_curve"]): { date: string; drawdown_pct: number }[] {
  let peak = -Infinity;
  return points.map((p) => {
    peak = Math.max(peak, p.strategy_equity);
    return { date: p.date, drawdown_pct: peak > 0 ? (p.strategy_equity / peak - 1) * 100 : 0 };
  });
}

export function BacktestPanel() {
  const initialRange = rangeForPreset("1Y");
  const [preset, setPreset] = useState<Preset>("1Y");
  const [tickers, setTickers] = useState<string[]>(TRAINED_TICKERS.map((t) => t.ticker));
  const [startDate, setStartDate] = useState(initialRange.start);
  const [endDate, setEndDate] = useState(initialRange.end);
  const [initialCapital, setInitialCapital] = useState("100000");
  const [strategy, setStrategy] = useState<Strategy>("max_sharpe");
  const [riskFreeRate, setRiskFreeRate] = useState("2");
  const [benchmark, setBenchmark] = useState<(typeof BENCHMARK_OPTIONS)[number]>("SPY");
  const [jobId, setJobId] = useState<string | null>(null);

  const startMutation = useMutation({
    mutationFn: startBacktestJob,
    retry: false,
    onSuccess: (res) => setJobId(res.job_id),
  });

  const statusQuery = useQuery({
    queryKey: ["backtest-job", jobId],
    queryFn: () => getBacktestJobStatus(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 400 : false),
    retry: false,
  });

  function handlePreset(p: Preset) {
    setPreset(p);
    if (p !== "custom") {
      const r = rangeForPreset(p);
      setStartDate(r.start);
      setEndDate(r.end);
    }
  }

  function toggleTicker(ticker: string) {
    setTickers((prev) => (prev.includes(ticker) ? prev.filter((t) => t !== ticker) : [...prev, ticker]));
  }

  function handleRun() {
    const capital = Number(initialCapital);
    const rf = Number(riskFreeRate);
    if (tickers.length === 0) return;
    setJobId(null);
    startMutation.mutate({
      tickers,
      start_date: startDate,
      end_date: endDate,
      initial_capital: Number.isFinite(capital) && capital > 0 ? capital : 100_000,
      strategy,
      risk_free_rate: Number.isFinite(rf) ? rf / 100 : 0,
      benchmark_ticker: benchmark === "None" ? null : benchmark,
    });
  }

  const job = statusQuery.data;
  const isRunning = startMutation.isPending || job?.status === "running";
  const data: BacktestResponse | null = job?.status === "done" ? job.result : null;

  const startErrorMessage =
    startMutation.error instanceof ApiError
      ? (startMutation.error.detail ?? startMutation.error.message)
      : startMutation.isError
        ? "Could not start the backtest."
        : null;
  const jobErrorMessage = job?.status === "error" ? job.error : null;
  const errorMessage = startErrorMessage ?? jobErrorMessage;

  const progress = job?.progress;
  const progressPct = progress && progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;
  const drawdown = data ? computeDrawdown(data.equity_curve) : [];

  return (
    <div className="flex flex-col gap-6">
      {/* Configuration */}
      <div className="rounded-md border border-line p-4">
        <SectionEyebrow>Configuration</SectionEyebrow>
        <div className="mb-1 mt-1 text-sm font-bold text-ink">Backtesting</div>
        <p className="mb-4 text-xs text-ink-faint">
          Walk-forward simulation of the app's own LSTM forecast + mean-variance optimization
          strategy, rebalanced every 22 trading days (the model's own forecast horizon). This is a
          historical simulation, not a prediction of future performance — see methodology below.
        </p>

        <div className="mb-4 flex flex-wrap gap-2">
          {TRAINED_TICKERS.map((t) => (
            <button
              key={t.ticker}
              type="button"
              onClick={() => toggleTicker(t.ticker)}
              className={`rounded border px-2.5 py-1 text-xs font-semibold transition-colors ${
                tickers.includes(t.ticker)
                  ? "border-accent-strong bg-ink-strong text-white"
                  : "border-line-strong text-ink-muted hover:bg-surface-alt hover:text-ink"
              }`}
              title={t.name}
            >
              {t.ticker}
            </button>
          ))}
        </div>

        <div className="mb-4 flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink">Period</span>
          <FilterGroup value={preset} onChange={handlePreset} options={PRESETS} />
        </div>

        <div className="flex flex-wrap items-end gap-4">
          {preset === "custom" && (
            <>
              <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                Start date
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className={`font-mono ${INPUT_CLASS}`}
                />
              </label>
              <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
                End date
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className={`font-mono ${INPUT_CLASS}`}
                />
              </label>
            </>
          )}
          {preset !== "custom" && (
            <div className="text-xs text-ink-faint">
              {startDate} → {endDate}
            </div>
          )}
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Initial capital ($)
            <input
              type="number"
              min="1"
              step="1000"
              value={initialCapital}
              onChange={(e) => setInitialCapital(e.target.value)}
              className={`w-36 font-mono ${INPUT_CLASS}`}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Strategy
            <select value={strategy} onChange={(e) => setStrategy(e.target.value as Strategy)} className={INPUT_CLASS}>
              {STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Risk-free rate (%)
            <input
              type="number"
              min="0"
              step="0.25"
              value={riskFreeRate}
              onChange={(e) => setRiskFreeRate(e.target.value)}
              className={`w-24 font-mono ${INPUT_CLASS}`}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
            Benchmark
            <select
              value={benchmark}
              onChange={(e) => setBenchmark(e.target.value as (typeof BENCHMARK_OPTIONS)[number])}
              className={INPUT_CLASS}
            >
              {BENCHMARK_OPTIONS.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </label>
          <Button onClick={handleRun} disabled={isRunning || tickers.length === 0}>
            {isRunning ? "Running…" : "Run backtest"}
          </Button>
        </div>
        {tickers.length === 0 && (
          <p className="mt-3 text-xs text-down">Select at least one ticker.</p>
        )}
        {errorMessage && (
          <p role="alert" className="mt-3 rounded bg-down-soft px-3 py-2 text-sm text-down">
            {errorMessage}
          </p>
        )}
      </div>

      {/* Progress */}
      {isRunning && (
        <div className="rounded-md border border-line p-6">
          <SectionEyebrow>Backtest running</SectionEyebrow>
          <div className="mt-3 flex flex-col gap-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-semibold text-ink">
                {progress ? PHASE_LABEL[progress.phase] ?? progress.phase : "Starting…"}
              </span>
              {progress && progress.phase === "simulating" && progress.total > 0 && (
                <span className="font-mono text-ink-muted">
                  {progress.completed} / {progress.total} rebalance periods
                </span>
              )}
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-alt">
              <div
                className="h-full rounded-full bg-accent-strong transition-all"
                style={{
                  width:
                    progress && progress.phase === "simulating" && progress.total > 0
                      ? `${progressPct}%`
                      : "8%",
                }}
              />
            </div>
            {progress?.phase === "simulating" && progress.period_start && progress.period_end && (
              <div className="text-xs text-ink-faint">
                Current period: <span className="font-mono text-ink-muted">{progress.period_start} → {progress.period_end}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Results */}
      {data && (
        <>
          <SectionEyebrow>Results</SectionEyebrow>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
            <StatTile label="Total Return" value={signedPercent(data.strategy_metrics.total_return_pct, 1)} />
            <StatTile
              label="Annualized Return"
              value={signedPercent(data.strategy_metrics.annualized_return_pct, 1)}
            />
            <StatTile label="Volatility" value={percent(data.strategy_metrics.annualized_volatility_pct, 1)} />
            <StatTile label="Sharpe Ratio" value={data.strategy_metrics.sharpe_ratio.toFixed(2)} />
            <StatTile label="Max Drawdown" value={signedPercent(data.strategy_metrics.max_drawdown_pct, 1)} />
            <StatTile label="Rebalance Count" value={String(data.rebalance_dates.length)} hint={`${data.num_trades} trades`} />
          </div>

          <SectionEyebrow>Equity Curve</SectionEyebrow>
          <div className="rounded-md border border-line">
            <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
              Strategy{data.inputs.benchmark_ticker ? ` vs. ${data.inputs.benchmark_ticker}` : ""}
            </div>
            <div className="p-2">
              <EquityCurveChart points={data.equity_curve} />
            </div>
          </div>

          <SectionEyebrow>Drawdown</SectionEyebrow>
          <div className="rounded-md border border-line">
            <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
              Underwater curve — % below running peak equity
            </div>
            <div className="p-2">
              <DrawdownChart points={drawdown} />
            </div>
          </div>

          <SectionEyebrow>Performance Summary</SectionEyebrow>
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-md border border-line p-4">
              <div className="mb-3 text-sm font-bold text-ink">Rebalance periods</div>
              <div className="flex flex-col gap-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-ink-muted">Winning periods</span>
                  <span className="font-mono font-semibold text-up">{data.winning_periods}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-ink-muted">Losing periods</span>
                  <span className="font-mono font-semibold text-down">{data.losing_periods}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-ink-muted">Flat periods</span>
                  <span className="font-mono font-semibold text-ink-muted">{data.flat_periods}</span>
                </div>
                <div className="flex items-center justify-between border-t border-line-soft pt-2">
                  <span className="text-ink-muted">Win rate</span>
                  <span className="font-mono font-semibold text-ink">
                    {data.win_rate_pct != null ? percent(data.win_rate_pct, 1) : "—"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-ink-muted">Period</span>
                  <span className="font-mono text-xs text-ink-muted">
                    {data.inputs.start_date} → {data.inputs.end_date}
                  </span>
                </div>
              </div>
            </div>

            {data.benchmark_metrics ? (
              <div className="rounded-md border border-line p-4">
                <div className="mb-3 text-sm font-bold text-ink">
                  Strategy vs. benchmark ({data.inputs.benchmark_ticker})
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-xs text-ink-faint">Strategy return</div>
                    <div className="font-mono font-semibold text-ink">
                      {signedPercent(data.strategy_metrics.total_return_pct, 1)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-ink-faint">Benchmark return</div>
                    <div className="font-mono font-semibold text-ink">
                      {signedPercent(data.benchmark_metrics.total_return_pct, 1)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-ink-faint">Strategy Sharpe</div>
                    <div className="font-mono font-semibold text-ink">
                      {data.strategy_metrics.sharpe_ratio.toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-ink-faint">Benchmark Sharpe</div>
                    <div className="font-mono font-semibold text-ink">
                      {data.benchmark_metrics.sharpe_ratio.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-md border border-dashed border-line p-4 text-center text-sm text-ink-muted">
                No benchmark selected for this run.
              </div>
            )}
          </div>

          <div className="rounded-md border border-line">
            <div className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink">
              Trade log ({data.trades.length})
            </div>
            <div className="max-h-64 overflow-x-auto overflow-y-auto">
              <table className="w-full min-w-[480px] text-xs">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-line text-left uppercase tracking-wide text-ink-faint">
                    <th className="px-3 py-2 font-semibold">Date</th>
                    <th className="px-3 py-2 font-semibold">Ticker</th>
                    <th className="px-3 py-2 font-semibold">Side</th>
                    <th className="px-3 py-2 font-semibold">Qty</th>
                    <th className="px-3 py-2 font-semibold">Price</th>
                    <th className="px-3 py-2 font-semibold">Notional</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line-soft font-mono">
                  {data.trades.map((t, i) => (
                    <tr key={i}>
                      <td className="px-3 py-1.5">{t.date}</td>
                      <td className="px-3 py-1.5 font-sans font-semibold text-ink">{t.ticker}</td>
                      <td className={`px-3 py-1.5 ${t.side === "BUY" ? "text-up" : "text-down"}`}>{t.side}</td>
                      <td className="px-3 py-1.5">{t.quantity.toFixed(2)}</td>
                      <td className="px-3 py-1.5">{money(t.price, 2)}</td>
                      <td className="px-3 py-1.5">{money(t.notional, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

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
    </div>
  );
}
