import { Link } from "react-router-dom";
import { Brand, Mark } from "../components/Brand";
import { buttonClass } from "../components/buttonStyles";

const FEATURES = [
  {
    title: "Market Intelligence",
    body: "Real ETF quotes, history and technical signals from Yahoo Finance.",
  },
  {
    title: "AI Forecasting",
    body: "Per-ticker LSTM return forecasting, with an honest fallback when a trained model isn't available.",
  },
  {
    title: "Portfolio Optimization",
    body: "Mean-variance optimization over real historical covariance — max Sharpe, min volatility, risk parity, equal weight.",
  },
  {
    title: "Paper Trading",
    body: "$250,000 in simulated capital. Real market prices, zero real orders.",
  },
  {
    title: "Risk Analysis",
    body: "Volatility, drawdown, correlation and the efficient frontier for your actual holdings.",
  },
  {
    title: "AI Assistant",
    body: "Ask about your portfolio, markets or news — answered from your real data, never fabricated.",
  },
];

// A fixed, deterministic set of OHLC values — purely illustrative chart
// art for the public landing page (explicitly labeled as such below; real
// candlesticks driven by live backend data belong to the signed-in Markets
// page). Not randomized so the page renders identically on every load.
const CANDLES: { open: number; high: number; low: number; close: number }[] = [
  { open: 40, high: 46, low: 38, close: 44 },
  { open: 44, high: 48, low: 41, close: 42 },
  { open: 42, high: 45, low: 36, close: 38 },
  { open: 38, high: 41, low: 33, close: 40 },
  { open: 40, high: 47, low: 39, close: 46 },
  { open: 46, high: 52, low: 44, close: 50 },
  { open: 50, high: 51, low: 45, close: 47 },
  { open: 47, high: 49, low: 42, close: 44 },
  { open: 44, high: 50, low: 43, close: 49 },
  { open: 49, high: 55, low: 48, close: 53 },
  { open: 53, high: 54, low: 48, close: 49 },
  { open: 49, high: 53, low: 46, close: 51 },
  { open: 51, high: 58, low: 50, close: 56 },
  { open: 56, high: 57, low: 51, close: 52 },
  { open: 52, high: 55, low: 49, close: 54 },
  { open: 54, high: 61, low: 53, close: 59 },
  { open: 59, high: 60, low: 54, close: 55 },
  { open: 55, high: 58, low: 52, close: 57 },
  { open: 57, high: 63, low: 56, close: 61 },
  { open: 61, high: 62, low: 56, close: 58 },
  { open: 58, high: 64, low: 57, close: 63 },
  { open: 63, high: 68, low: 61, close: 66 },
  { open: 66, high: 67, low: 61, close: 63 },
  { open: 63, high: 70, low: 62, close: 68 },
];

function CandlestickIllustration() {
  const width = 320;
  const height = 96;
  const min = Math.min(...CANDLES.map((c) => c.low));
  const max = Math.max(...CANDLES.map((c) => c.high));
  const pad = 6;
  const scaleY = (v: number) => height - pad - ((v - min) / (max - min)) * (height - pad * 2);
  const step = width / CANDLES.length;
  const bodyWidth = step * 0.55;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-24 w-full"
      role="img"
      aria-label="Illustrative candlestick chart"
    >
      {[0.25, 0.5, 0.75].map((f) => (
        <line
          key={f}
          x1={0}
          x2={width}
          y1={height * f}
          y2={height * f}
          style={{ stroke: "var(--color-line)" }}
          strokeWidth={1}
        />
      ))}
      {CANDLES.map((c, i) => {
        const x = i * step + step / 2;
        const up = c.close >= c.open;
        const color = up ? "var(--color-up)" : "var(--color-down)";
        const bodyTop = scaleY(Math.max(c.open, c.close));
        const bodyBottom = scaleY(Math.min(c.open, c.close));
        return (
          <g key={i}>
            <line
              x1={x}
              x2={x}
              y1={scaleY(c.high)}
              y2={scaleY(c.low)}
              style={{ stroke: color }}
              strokeWidth={1}
            />
            <rect
              x={x - bodyWidth / 2}
              y={bodyTop}
              width={bodyWidth}
              height={Math.max(bodyBottom - bodyTop, 1.5)}
              style={{ fill: color }}
            />
          </g>
        );
      })}
    </svg>
  );
}

const STEPS = [
  { n: "01", title: "Explore the market", body: "Browse real ETF quotes, history and technical signals." },
  { n: "02", title: "Analyze with AI", body: "Get LSTM-based return forecasts and news-driven sentiment." },
  { n: "03", title: "Optimize your portfolio", body: "Generate risk-aware allocations with mean-variance optimization." },
  { n: "04", title: "Simulate your strategy", body: "Place paper orders and track performance over time." },
];

export function LandingPage() {
  return (
    <div className="theme-light-forced min-h-screen bg-surface text-ink">
      <nav className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Brand size="sm" />
          <div className="hidden items-center gap-7 text-sm font-medium text-ink-muted md:flex">
            <a href="#markets" className="hover:text-ink">Markets</a>
            <a href="#intelligence" className="hover:text-ink">Intelligence</a>
            <a href="#how-it-works" className="hover:text-ink">How it works</a>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/login" className={buttonClass("secondary", "px-3.5 py-1.5")}>
              Log in
            </Link>
            <Link to="/register" className={buttonClass("primary", "px-3.5 py-1.5")}>
              Create account
            </Link>
          </div>
        </div>
      </nav>

      <header className="mx-auto grid max-w-6xl gap-10 px-4 py-16 md:grid-cols-2 md:items-center">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-line px-3 py-1 text-xs font-bold uppercase tracking-widest text-ink-muted">
            Optiport
          </span>
          <h1 className="mt-4 text-4xl font-extrabold leading-tight tracking-tight md:text-5xl">
            AI-Powered Portfolio Intelligence
          </h1>
          <p className="mt-4 max-w-md text-base leading-relaxed text-ink-muted">
            AI-powered ETF portfolio intelligence and paper trading — real market data,
            forecasting, news analysis and portfolio optimization in one platform.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/register" className={buttonClass("primary", "px-5 py-2.5")}>
              Create account
            </Link>
            <a href="#markets" className={buttonClass("secondary", "px-5 py-2.5")}>
              Explore Markets
            </a>
            <Link
              to="/login"
              className="rounded px-5 py-2.5 text-sm font-bold text-ink-muted hover:text-ink"
            >
              Log in
            </Link>
          </div>
        </div>

        <div id="markets" className="rounded-md border border-line">
          <div className="flex items-baseline justify-between border-b border-line px-4 py-3">
            <div>
              <span className="font-mono text-sm font-bold">SPY</span>
              <span className="ml-2 text-xs text-ink-faint">S&amp;P 500</span>
            </div>
            <div className="text-right">
              <span className="font-mono text-lg font-bold">642.31</span>
              <span className="ml-2 font-mono text-sm font-bold text-up">+1.24%</span>
            </div>
          </div>
          <div className="border-b border-line px-4 py-3">
            <CandlestickIllustration />
          </div>
          <div className="divide-y divide-line-soft">
            {["QQQ", "PSI", "IYW", "NLR"].map((ticker, i) => (
              <div key={ticker} className="flex items-center justify-between px-4 py-2.5">
                <span className="font-mono text-sm font-bold">{ticker}</span>
                <span
                  className={`font-mono text-sm font-bold ${i % 3 === 1 ? "text-down" : "text-up"}`}
                >
                  {i % 3 === 1 ? "-0.42%" : "+0.87%"}
                </span>
              </div>
            ))}
          </div>
          <p className="border-t border-line px-4 py-2.5 text-xs text-ink-faint">
            Illustrative — real-time quotes are available once you're signed in.
          </p>
        </div>
      </header>

      <section id="intelligence" className="border-t border-line bg-surface-alt px-4 py-16">
        <div className="mx-auto max-w-6xl">
          <div className="mb-10 max-w-xl">
            <span className="text-xs font-bold uppercase tracking-widest text-ink-faint">Platform</span>
            <h2 className="mt-2 text-2xl font-extrabold tracking-tight">
              Everything you need to invest with data
            </h2>
          </div>
          <div className="grid gap-px overflow-hidden rounded-md border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-surface p-6">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded border border-ink">
                  <Mark size={16} />
                </div>
                <h3 className="mb-1 text-sm font-bold">{f.title}</h3>
                <p className="text-sm leading-relaxed text-ink-muted">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="px-4 py-16">
        <div className="mx-auto max-w-6xl">
          <div className="mb-10 max-w-xl">
            <span className="text-xs font-bold uppercase tracking-widest text-ink-faint">Workflow</span>
            <h2 className="mt-2 text-2xl font-extrabold tracking-tight">How it works</h2>
          </div>
          <div className="grid gap-7 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <div key={s.n}>
                <span className="mb-3 block border-b-2 border-ink pb-2 font-mono text-sm font-bold text-ink-faint">
                  {s.n}
                </span>
                <h4 className="mb-1 text-sm font-bold">{s.title}</h4>
                <p className="text-sm leading-relaxed text-ink-muted">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-line px-4 py-16">
        <div className="mx-auto max-w-6xl rounded-md bg-ink px-6 py-12 text-center">
          <h2 className="mb-6 text-2xl font-extrabold tracking-tight text-white">
            Ready to build your portfolio?
          </h2>
          <Link
            to="/register"
            className="inline-block rounded bg-white px-6 py-2.5 text-sm font-bold text-ink hover:bg-surface-soft"
          >
            Create your account
          </Link>
        </div>
      </section>

      <footer className="border-t border-line px-4 py-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 text-sm text-ink-faint">
          <div>
            <strong className="text-ink">OPTIPORT</strong> · ETF portfolio intelligence, simulated
            trading, © 2026
          </div>
          <div className="flex gap-5">
            <a href="#markets" className="hover:text-ink">Markets</a>
            <a href="#intelligence" className="hover:text-ink">Intelligence</a>
            <a href="#how-it-works" className="hover:text-ink">How it works</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
