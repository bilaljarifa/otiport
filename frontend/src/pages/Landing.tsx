import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Brand, Mark } from "../components/Brand";
import { buttonClass } from "../components/buttonStyles";
import { CandlestickChart } from "../components/CandlestickChart";
import { StatTile } from "../components/StatTile";
import { useScrollReveal } from "../hooks/useScrollReveal";
import { usePublicMarketTicker } from "../lib/queries";
import { ETF_UNIVERSE } from "../lib/catalog";

/**
 * The top market ticker is the one real, live piece of data on this public
 * page — `GET /public/market/quotes` (unauthenticated, fixed 14-ticker
 * universe, no user/account context) via `usePublicMarketTicker`. Every
 * other number below it is a static, clearly-labeled illustration or copy
 * describing what the real, authenticated app does — the rest of the
 * backend (portfolio/forecast/news/etc.) all requires a signed-in session
 * (`_AUTH` on almost every other route), so nothing else here calls the API.
 */

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Real-time, not fabricated: derives "is the NYSE open right now" purely
 * from the current wall-clock time in America/New_York — a presentational
 * label only, never used to decide whether to fetch or show data. */
function isUsMarketOpenNow(): boolean {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    hour: "numeric",
    minute: "numeric",
    hour12: false,
    weekday: "short",
  }).formatToParts(new Date());
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const weekday = get("weekday");
  const hour = Number(get("hour"));
  const minute = Number(get("minute"));
  if (weekday === "Sat" || weekday === "Sun") return false;
  const minutesSinceMidnight = hour * 60 + minute;
  return minutesSinceMidnight >= 9 * 60 + 30 && minutesSinceMidnight < 16 * 60;
}

/** "Updated Xs/Xm ago", re-rendering every second — a local UI timer, never
 * an extra request; the underlying data only actually refreshes on
 * `usePublicMarketTicker`'s own staleTime/refetchInterval. */
function useRelativeTime(sinceMs: number | undefined): string {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!sinceMs || prefersReducedMotion()) return;
    const id = setInterval(() => setTick((t) => t + 1), 1_000);
    return () => clearInterval(id);
  }, [sinceMs]);

  if (!sinceMs) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - sinceMs) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ago`;
}

function Reveal({
  children,
  className = "",
  stagger = false,
}: {
  children: ReactNode;
  className?: string;
  stagger?: boolean;
}) {
  const ref = useScrollReveal<HTMLDivElement>();
  return (
    <div ref={ref} className={`${stagger ? "reveal-stagger" : "reveal"} ${className}`}>
      {children}
    </div>
  );
}

// Fixed, deterministic illustrative candles — the real chart component
// (`CandlestickChart`, identical to the one on Markets/Portfolio once
// signed in), fed static data so the page renders identically every load.
function buildIllustrativeBars(closes: number[], startISO: string, stepDays: number) {
  const start = new Date(startISO);
  return closes.map((close, i) => {
    const open = i === 0 ? close - 3 : closes[i - 1];
    const high = Math.max(open, close) + 2 + (i % 3);
    const low = Math.min(open, close) - 2 - (i % 2);
    const date = new Date(start);
    date.setUTCDate(start.getUTCDate() + i * stepDays);
    return { time: date.toISOString().slice(0, 10), open, high, low, close, volume: 1_200_000 + (i % 5) * 180_000 };
  });
}

const ILLUSTRATIVE_BARS = buildIllustrativeBars(
  [40, 44, 42, 38, 40, 46, 50, 47, 44, 49, 53, 49, 51, 56, 52, 54, 59, 55, 57, 61, 58, 63, 66, 63, 68],
  "2026-04-01T00:00:00Z",
  3,
);

const ALLOCATIONS: { ticker: string; name: string; weight: number; signal: string }[] = [
  { ticker: "RING", name: "Gold Miners", weight: 49, signal: "Strong Buy" },
  { ticker: "GUNR", name: "Global Resources", weight: 32, signal: "Strong Buy" },
  { ticker: "PSI", name: "Semiconductors", weight: 13, signal: "Hold" },
  { ticker: "IYW", name: "US Technology", weight: 6, signal: "Avoid" },
];

const TRADING_STEPS = [
  { value: "$250,000", label: "Simulated capital" },
  { value: "Choose ETFs", label: "12-ticker universe" },
  { value: "Build portfolio", label: "Optimize allocation" },
  { value: "Execute trades", label: "Real market prices" },
  { value: "Track performance", label: "Positions & P&L" },
];

const ASSISTANT_QUESTIONS = [
  "What is my current portfolio value?",
  "Why did my portfolio move today?",
  "How is SPY affected by the latest news?",
  "What is my current portfolio allocation?",
];

const FEATURES: { title: string; body: string; icon: (props: { className?: string }) => ReactNode }[] = [
  { title: "Market Data", body: "Real ETF quotes, history and technical signals from Yahoo Finance.", icon: MarketIcon },
  { title: "Portfolio Analytics", body: "Volatility, drawdown, correlation and the efficient frontier for your holdings.", icon: AnalyticsIcon },
  { title: "ETF Forecasting", body: "Per-ticker LSTM models predicting 22-day returns from price history.", icon: ForecastIcon },
  { title: "News Intelligence", body: "Sentiment, recency and market-impact scoring layered onto every forecast.", icon: NewsIcon },
  { title: "Paper Trading", body: "$250,000 in simulated capital. Real fill prices, zero real risk.", icon: TradingIcon },
  { title: "AI Assistant", body: "Ask about your positions, markets or news — answered from your real data.", icon: AssistantIcon },
];

function ChangeTag({ value, className = "" }: { value: number; className?: string }) {
  const tone = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-ink-faint";
  return (
    <span className={`font-mono font-bold ${tone} ${className}`}>
      {value > 0 ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}

const TICKER_NAMES = new Map(ETF_UNIVERSE.map((e) => [e.ticker, e.name]));

/** The one live section of this page — real quotes from
 * `GET /public/market/quotes` (unauthenticated, fixed ticker list, see
 * `api.py::public_market_quotes`). Never fabricates a price: a ticker
 * missing from the response (fetch failure, market data momentarily
 * unavailable) is simply left out rather than shown with a made-up value,
 * and if none come back at all the strip renders nothing instead of a
 * fake row. Content is duplicated once so the CSS marquee (`.ticker-track`,
 * `translateX(-50%)`) loops seamlessly with no jump. */
function TickerTape() {
  const ticker = usePublicMarketTicker();

  if (ticker.isLoading) {
    return (
      <div className="overflow-hidden border-b border-line bg-surface py-2.5" aria-hidden="true">
        <div className="mx-auto flex max-w-6xl items-center gap-8 px-6">
          {Array.from({ length: 7 }).map((_, i) => (
            <span key={i} className="h-4 w-32 shrink-0 animate-pulse rounded bg-surface-alt" />
          ))}
        </div>
      </div>
    );
  }

  const quotes = ticker.data?.quotes ?? {};
  const items = ETF_UNIVERSE.map((e) => quotes[e.ticker]).filter((q): q is NonNullable<typeof q> => Boolean(q));

  if (items.length === 0) return null;

  const doubled = [...items, ...items];
  return (
    <div className="overflow-hidden border-b border-line bg-surface py-2.5" role="group" aria-label="Live ETF price ticker">
      <div className="ticker-track flex w-max items-center gap-8">
        {doubled.map((q, i) => (
          <span key={`${q.ticker}-${i}`} className="flex items-baseline gap-2 whitespace-nowrap px-2">
            <span className="font-mono text-sm font-bold text-ink">{q.ticker}</span>
            <span className="text-xs text-ink-faint">{TICKER_NAMES.get(q.ticker) ?? ""}</span>
            <span className="font-mono text-sm font-semibold text-ink">${q.price.toFixed(2)}</span>
            <ChangeTag value={q.change_pct} className="text-sm" />
          </span>
        ))}
      </div>
    </div>
  );
}

/** Deterministic per-ticker walk, purely so each rotated card gets a
 * distinct, stable illustrative shape (never real history — no public
 * endpoint serves that here) — same seed always produces the same shape. */
function deterministicTrendPoints(seed: string, length = 15): number[] {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  const points: number[] = [50];
  for (let i = 1; i < length; i++) {
    h = (h * 1103515245 + 12345) >>> 0;
    const delta = ((h % 700) / 100) - 3.5;
    points.push(Math.max(10, Math.min(90, points[i - 1] + delta)));
  }
  return points;
}

/** The color follows the ticker's real `change_pct` sign — only the shape
 * is illustrative, so this never visually contradicts the real number
 * shown next to it. */
function HeroSparkline({ seed, positive }: { seed: string; positive: boolean }) {
  const width = 220;
  const height = 64;
  const values = useMemo(() => deterministicTrendPoints(seed), [seed]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const step = width / (values.length - 1);
  const points = values
    .map((v, i) => `${i * step},${height - ((v - min) / (max - min || 1)) * (height - 6) - 3}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-16 w-full" role="img" aria-label="Illustrative trend shape, not historical price data">
      <polyline
        points={points}
        fill="none"
        stroke={positive ? "var(--color-up)" : "var(--color-down)"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const FEATURED_TICKERS = ["PSI", "SPY", "QQQ", "RING", "GUNR", "IYW"];
const ROTATE_INTERVAL_MS = 6_000;

/** The hero's own live quote card — same real `/public/market/quotes` data
 * source as `TickerTape` (shared query cache, no extra request), cycling
 * through a handful of featured tickers so the hero reads as a live feed
 * rather than one static number. Never falls back to a fabricated price:
 * a missing/failed fetch shows an honest state instead of a stale or
 * invented quote, and rotation pauses entirely under
 * `prefers-reduced-motion`. */
function HeroQuoteCard() {
  const ticker = usePublicMarketTicker();
  const quotes = ticker.data?.quotes ?? {};
  const available = FEATURED_TICKERS.filter((t) => quotes[t]);
  const pool = available.length > 0 ? available : Object.keys(quotes);

  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (pool.length <= 1 || prefersReducedMotion()) return;
    const id = setInterval(() => setIndex((i) => (i + 1) % pool.length), ROTATE_INTERVAL_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pool.length]);

  const relativeTime = useRelativeTime(ticker.dataUpdatedAt);

  if (ticker.isLoading) {
    return (
      <div className="hero-enter hero-enter-delay-2 rounded-xl border border-line bg-surface p-5 shadow-[0_24px_48px_-24px_rgb(0_0_0_/_0.22)]">
        <div className="h-8 w-40 animate-pulse rounded bg-surface-alt" />
        <div className="mt-3 h-16 w-full animate-pulse rounded bg-surface-alt" />
      </div>
    );
  }

  if (ticker.isError || pool.length === 0) {
    return (
      <div className="hero-enter hero-enter-delay-2 rounded-xl border border-line bg-surface p-5 shadow-[0_24px_48px_-24px_rgb(0_0_0_/_0.22)]">
        <p className="text-sm font-semibold text-ink">Market data unavailable</p>
        <p className="mt-1.5 text-xs text-ink-faint">Live quotes are temporarily unreachable — the rest of the platform is unaffected.</p>
      </div>
    );
  }

  const featured = quotes[pool[index % pool.length]];
  if (!featured) return null;
  const marketOpen = isUsMarketOpenNow();

  return (
    <div className="hero-enter hero-enter-delay-2 rounded-xl border border-line bg-surface p-5 shadow-[0_24px_48px_-24px_rgb(0_0_0_/_0.22)]">
      <div className="mb-1 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide">
        <span className={`inline-flex items-center gap-1.5 ${marketOpen ? "text-up" : "text-ink-faint"}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${marketOpen ? "status-pulse bg-up" : "bg-ink-faint"}`} aria-hidden="true" />
          {marketOpen ? "Market open" : "Market closed"}
        </span>
        {relativeTime && <span className="text-ink-faint">Updated {relativeTime}</span>}
      </div>
      <div className="flex items-baseline justify-between">
        <div>
          <span className="font-mono text-sm font-bold text-ink">{featured.ticker}</span>
          <span className="ml-2 text-xs text-ink-faint">{TICKER_NAMES.get(featured.ticker) ?? ""}</span>
        </div>
        <span className="flex items-baseline gap-2">
          <span className="font-mono text-lg font-bold text-ink">{featured.price.toFixed(2)}</span>
          <ChangeTag value={featured.change_pct} className="text-sm" />
        </span>
      </div>
      <div className="mt-3">
        <HeroSparkline seed={featured.ticker} positive={featured.change_pct >= 0} />
      </div>
      <p className="mt-3 text-xs text-ink-faint">Live market data · rotating through the ETF universe.</p>
    </div>
  );
}

const LIVE_MARKET_TICKERS = ["SPY", "QQQ", "PSI", "IYW", "RING", "GUNR"];

/** A real multi-ETF grid — same `/public/market/quotes` query/cache as the
 * ticker tape and hero card (no extra request). The per-row bar is derived
 * entirely from that ticker's own real `change_pct` (its width scales with
 * the real magnitude, capped so a large move doesn't overflow the row) —
 * never a fabricated historical chart, since no public endpoint serves
 * real intraday/historical bars here. */
function LiveMarketGrid() {
  const ticker = usePublicMarketTicker();
  const relativeTime = useRelativeTime(ticker.dataUpdatedAt);

  if (ticker.isLoading) {
    return (
      <div className="rounded-xl border border-line bg-surface p-5 shadow-[0_24px_48px_-24px_rgb(0_0_0_/_0.2)]">
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-11 w-full animate-pulse rounded bg-surface-alt" />
          ))}
        </div>
      </div>
    );
  }

  const quotes = ticker.data?.quotes ?? {};
  const rows = LIVE_MARKET_TICKERS.map((t) => quotes[t]).filter((q): q is NonNullable<typeof q> => Boolean(q));

  if (ticker.isError || rows.length === 0) {
    return (
      <div className="rounded-xl border border-line bg-surface p-5 shadow-[0_24px_48px_-24px_rgb(0_0_0_/_0.2)]">
        <p className="text-sm font-semibold text-ink">Market data unavailable</p>
        <p className="mt-1.5 text-xs text-ink-faint">Live quotes are temporarily unreachable — try again shortly.</p>
      </div>
    );
  }

  const maxMagnitude = Math.max(...rows.map((q) => Math.abs(q.change_pct)), 1);
  const marketOpen = isUsMarketOpenNow();

  return (
    <div className="rounded-xl border border-line bg-surface p-5 shadow-[0_24px_48px_-24px_rgb(0_0_0_/_0.2)]">
      <div className="mb-3 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide">
        <span className={`inline-flex items-center gap-1.5 ${marketOpen ? "text-up" : "text-ink-faint"}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${marketOpen ? "status-pulse bg-up" : "bg-ink-faint"}`} aria-hidden="true" />
          {marketOpen ? "Market open" : "Market closed"}
        </span>
        {relativeTime && <span className="text-ink-faint">Updated {relativeTime}</span>}
      </div>
      <div className="flex flex-col divide-y divide-line-soft">
        {rows.map((q) => {
          const positive = q.change_pct >= 0;
          const barWidth = (Math.abs(q.change_pct) / maxMagnitude) * 100;
          return (
            <div key={q.ticker} className="flex items-center gap-2 py-2.5 sm:gap-3">
              <div className="w-14 shrink-0 sm:w-24">
                <div className="font-mono text-sm font-bold text-ink">{q.ticker}</div>
                <div className="hidden truncate text-[11px] text-ink-faint sm:block">{TICKER_NAMES.get(q.ticker) ?? ""}</div>
              </div>
              <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-line-soft">
                <div
                  className={`h-full rounded-full transition-[width] duration-700 ease-out ${positive ? "bg-up" : "bg-down"}`}
                  style={{ width: `${Math.max(barWidth, 4)}%` }}
                />
              </div>
              <div className="w-16 shrink-0 text-right font-mono text-sm font-semibold text-ink sm:w-24">
                ${q.price.toFixed(2)}
              </div>
              <div className="w-12 shrink-0 text-right sm:w-16">
                <ChangeTag value={q.change_pct} className="text-xs" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function LandingPage() {
  return (
    <div className="theme-light-forced min-h-screen bg-surface text-ink">
      {/* 1. LIVE MARKET TICKER — the very first thing a visitor sees, above the nav */}
      <div id="ticker">
        <TickerTape />
      </div>

      {/* 11. NAVIGATION */}
      <nav className="sticky top-0 z-20 border-b border-line bg-surface/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
          <Brand size="sm" />
          <div className="hidden items-center gap-8 text-sm font-medium text-ink-muted md:flex">
            <a href="#ticker" className="transition-colors hover:text-ink">Markets</a>
            <a href="#optimization" className="transition-colors hover:text-ink">Analytics</a>
            <a href="#ai-assistant" className="transition-colors hover:text-ink">AI</a>
            <Link to="/pricing" className="transition-colors hover:text-ink">Pricing</Link>
          </div>
          <div className="flex items-center gap-1 sm:gap-2">
            <Link to="/pricing" className="rounded px-2 py-1.5 text-xs font-semibold text-ink-muted transition-colors hover:text-ink sm:text-sm md:hidden">
              Pricing
            </Link>
            <Link to="/login" className="rounded px-2 py-1.5 text-xs font-semibold text-ink-muted transition-colors hover:text-ink sm:px-3.5 sm:text-sm">
              Sign in
            </Link>
            <Link to="/register" className={buttonClass("primary", "px-2.5 py-1.5 text-xs sm:px-4 sm:text-sm")}>
              Create account
            </Link>
          </div>
        </div>
      </nav>

      {/* 1. HERO */}
      <header className="mx-auto grid max-w-6xl gap-12 px-6 pb-20 pt-20 sm:pt-28 md:grid-cols-[1.1fr_0.9fr] md:items-center">
        <div>
          <span className="hero-enter inline-flex items-center gap-2 rounded-full border border-line px-3.5 py-1 text-xs font-bold uppercase tracking-widest text-ink-muted">
            ETF portfolio intelligence
          </span>
          <h1 className="hero-enter hero-enter-delay-1 mt-6 text-5xl font-extrabold leading-[1.04] tracking-tight sm:text-6xl">
            Understand the market.
            <br />
            Build with confidence.
          </h1>
          <p className="hero-enter hero-enter-delay-2 mt-6 max-w-lg text-base leading-relaxed text-ink-muted">
            Optiport combines real ETF market data, mean-variance portfolio optimization,
            per-ticker LSTM forecasting and news-driven sentiment context — then lets you
            trade the strategy with $250,000 in simulated capital.
          </p>
          <div className="hero-enter hero-enter-delay-3 mt-8 flex flex-wrap items-center gap-3">
            <Link to="/register" className={buttonClass("primary", "px-6 py-3 text-base")}>
              Create account
            </Link>
            <a href="#showcase" className={buttonClass("secondary", "px-6 py-3 text-base")}>
              Explore platform
            </a>
            <Link to="/pricing" className="px-2 py-3 text-sm font-semibold text-ink-muted underline underline-offset-4 transition-colors hover:text-ink">
              View pricing →
            </Link>
          </div>
        </div>

        <HeroQuoteCard />
      </header>

      {/* 3. PRODUCT SHOWCASE — visual centerpiece */}
      <section id="showcase" className="px-6 pb-24 pt-20">
        <Reveal className="mx-auto max-w-2xl text-center">
          <span className="text-xs font-bold uppercase tracking-widest text-ink-faint">The platform</span>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
            Everything you need to understand your portfolio.
          </h2>
        </Reveal>

        <Reveal className="mx-auto mt-12 max-w-6xl">
          <div className="overflow-hidden rounded-xl border border-line shadow-[0_40px_80px_-32px_rgb(0_0_0_/_0.28)]">
            <div className="flex items-center gap-1.5 border-b border-line bg-surface-alt px-4 py-3">
              <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
              <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
              <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
              <span className="ml-3 font-mono text-xs text-ink-faint">optiport.app/app/dashboard</span>
              <span className="ml-auto rounded-full border border-line-strong px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-faint">
                Illustrative platform preview
              </span>
            </div>
            <div className="grid md:grid-cols-[200px_1fr]">
              <div className="hidden flex-col gap-1 border-r border-line bg-surface-alt p-4 md:flex">
                <div className="mb-4 flex items-center gap-2 px-2">
                  <Mark size={18} />
                  <span className="text-xs font-extrabold tracking-wide">OPTIPORT</span>
                </div>
                {["Dashboard", "Markets", "Portfolio", "Trading", "Analytics", "News", "AI Assistant"].map((item, i) => (
                  <span key={item} className={`rounded px-2.5 py-1.5 text-xs font-medium ${i === 0 ? "bg-accent-soft text-ink" : "text-ink-muted"}`}>
                    {item}
                  </span>
                ))}
              </div>
              <div className="p-5 sm:p-7">
                <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <StatTile label="Portfolio value" value="$267,940" delta={{ value: "+7.18%", positive: true }} hint="all-time" />
                  <StatTile label="Today's P&amp;L" value="+$1,204" delta={{ value: "+0.45%", positive: true }} />
                  <StatTile label="Cash available" value="$41,205" hint="ready to deploy" />
                </div>
                <div className="rounded-md border border-line p-3 sm:p-4">
                  <div className="mb-2 flex items-baseline justify-between">
                    <span className="font-mono text-sm font-bold">PSI · Semiconductors</span>
                    <span className="flex items-baseline gap-2">
                      <span className="font-mono text-base font-bold">128.72</span>
                      <ChangeTag value={2.31} className="text-sm" />
                    </span>
                  </div>
                  <CandlestickChart bars={ILLUSTRATIVE_BARS} height={200} />
                </div>
                <div className="mt-3 divide-y divide-line-soft rounded-md border border-line text-sm">
                  {[
                    { t: "RING", n: "Gold Miners", w: "49%", c: 13.6 },
                    { t: "GUNR", n: "Global Resources", w: "32%", c: 21.4 },
                    { t: "PSI", n: "Semiconductors", w: "13%", c: 55.4 },
                  ].map((h) => (
                    <div key={h.t} className="flex items-center justify-between px-3 py-2">
                      <span className="flex items-baseline gap-2">
                        <span className="font-mono font-bold text-ink">{h.t}</span>
                        <span className="text-xs text-ink-faint">{h.n}</span>
                      </span>
                      <span className="flex items-baseline gap-3">
                        <span className="font-mono text-xs text-ink-faint">{h.w}</span>
                        <ChangeTag value={h.c} className="text-xs" />
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <p className="mt-4 text-center text-xs text-ink-faint">
            The real Optiport interface, shown with illustrative values — sign in to see your own portfolio, positions and quotes.
          </p>
        </Reveal>
      </section>

      {/* 4. MARKET INTELLIGENCE */}
      <section className="border-t border-line bg-surface-alt px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="grid min-w-0 gap-10 md:grid-cols-2 md:items-center">
            <Reveal className="min-w-0">
              <span className="text-xs font-bold uppercase tracking-widest text-ink-faint">Market intelligence</span>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">See the market clearly.</h2>
              <p className="mt-4 max-w-md text-base leading-relaxed text-ink-muted">
                Every chart is built from real historical prices — open, high, low, close and
                volume — fetched server-side from Yahoo Finance for the full ETF universe.
              </p>
              <ul className="mt-6 flex flex-col gap-3 text-sm text-ink-muted">
                {["Historical OHLC price bars", "Volume alongside every move", "Technical signals per ETF", "A curated 14-ticker sector universe"].map((item) => (
                  <li key={item} className="flex items-start gap-2.5">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-ink" />
                    {item}
                  </li>
                ))}
              </ul>
            </Reveal>
            <Reveal className="min-w-0">
              <LiveMarketGrid />
            </Reveal>
          </div>
        </div>
      </section>

      {/* 5. FORECASTING + NEWS CONTEXT */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <Reveal className="mx-auto max-w-2xl text-center">
            <span className="text-xs font-bold uppercase tracking-widest text-ink-faint">Forecasting</span>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
              Two forecasts, one clear picture.
            </h2>
            <p className="mt-4 text-base leading-relaxed text-ink-muted">
              A dedicated LSTM model per ETF predicts 22-day returns from technical history.
              A second layer scores today's news and applies a small, bounded adjustment — so
              you can see exactly how much of a forecast comes from price action versus
              current events.
            </p>
          </Reveal>

          <Reveal stagger className="mx-auto mt-14 grid max-w-4xl gap-6 sm:grid-cols-2">
            <FlowColumn
              eyebrow="Base Forecast"
              steps={["LSTM Model", "22-day price history"]}
              result="+4.9%"
              resultLabel="predicted 22-day return · PSI"
              tone="neutral"
            />
            <FlowColumn
              eyebrow="News-Context Forecast"
              steps={["Sentiment + recency", "Market-impact scoring"]}
              result="+5.2%"
              resultLabel="+0.3 pt adjustment · capped ±2 pt"
              tone="accent"
            />
          </Reveal>
          <p className="mt-6 text-center text-xs text-ink-faint">
            Illustrative example. News sentiment and market impact are probabilistic
            estimates — they do not guarantee future price movements.
          </p>
        </div>
      </section>

      {/* 6. PORTFOLIO OPTIMIZATION */}
      <section id="optimization" className="border-t border-line bg-surface-alt px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-12 md:grid-cols-2 md:items-center">
            <Reveal>
              <span className="text-xs font-bold uppercase tracking-widest text-ink-faint">Optimization</span>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight">Build a portfolio around your risk.</h2>
              <p className="mt-4 text-base leading-relaxed text-ink-muted">
                Optiport runs real historical covariance and forecasted returns through a
                portfolio optimizer — max Sharpe, minimum volatility, risk parity or equal
                weight — so you can analyze risk, compare allocations and simulate a trade
                plan before committing simulated capital.
              </p>
            </Reveal>
            <Reveal className="rounded-md border border-line bg-surface p-6">
              <div className="mb-4 flex items-baseline justify-between">
                <span className="text-xs font-bold uppercase tracking-widest text-ink-faint">Max Sharpe allocation</span>
                <span className="font-mono text-xs text-ink-faint">Sharpe 4.73</span>
              </div>
              <div className="flex flex-col gap-3">
                {ALLOCATIONS.map((a) => (
                  <div key={a.ticker}>
                    <div className="mb-1 flex items-baseline justify-between text-sm">
                      <span className="font-mono font-bold">{a.ticker}</span>
                      <span className="text-ink-faint">{a.name}</span>
                      <span className="font-mono font-bold">{a.weight}%</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-line-soft">
                      <div className="h-full rounded-full bg-accent-strong transition-[width] duration-700 ease-out" style={{ width: `${a.weight}%` }} />
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-5 text-xs text-ink-faint">
                Illustrative output — real allocations are computed from your chosen ETF universe and strategy in Analytics.
              </p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* 7. PAPER TRADING */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <Reveal className="mx-auto max-w-2xl text-center">
            <span className="text-xs font-bold uppercase tracking-widest text-ink-faint">Paper trading</span>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">Trade the strategy, risk nothing real.</h2>
            <p className="mt-4 text-base leading-relaxed text-ink-muted">
              Every account starts simulated. Orders fill at real market prices fetched by
              the backend — never a price the client sends.
            </p>
          </Reveal>

          <Reveal stagger className="mx-auto mt-14 flex max-w-5xl flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
            {TRADING_STEPS.map((s, i) => (
              <div key={s.value} className="flex flex-1 items-center gap-3 sm:flex-col sm:gap-2 sm:text-center">
                <div className="flex-1 rounded-md border border-line bg-surface px-4 py-3 sm:w-full">
                  <div className="font-mono text-sm font-bold text-ink">{s.value}</div>
                  <div className="mt-0.5 text-xs text-ink-faint">{s.label}</div>
                </div>
                {i < TRADING_STEPS.length - 1 && (
                  <ArrowIcon className="h-4 w-4 shrink-0 text-ink-faint sm:-rotate-90" />
                )}
              </div>
            ))}
          </Reveal>
          <p className="mt-6 text-center text-xs text-ink-faint">Simulated paper trading — no real orders are ever transmitted to a broker.</p>
        </div>
      </section>

      {/* 8. AI ASSISTANT */}
      <section id="ai-assistant" className="border-t border-line bg-surface-alt px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-10 md:grid-cols-2 md:items-center">
            <Reveal>
              <span className="text-xs font-bold uppercase tracking-widest text-ink-faint">AI Assistant</span>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight">Ask, don't dig through tabs.</h2>
              <p className="mt-4 max-w-md text-base leading-relaxed text-ink-muted">
                Once signed in, the assistant answers using your actual account — real
                positions, real quotes, real news, real forecasts. It never fabricates a
                number it can't retrieve.
              </p>
            </Reveal>
            <Reveal className="rounded-xl border border-line bg-surface p-5 shadow-[0_24px_48px_-24px_rgb(0_0_0_/_0.2)]">
              <div className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-ink-faint">
                <AssistantIcon className="h-3.5 w-3.5" />
                Example questions
              </div>
              <div className="flex flex-col gap-2.5">
                {ASSISTANT_QUESTIONS.map((q) => (
                  <div key={q} className="rounded-md border border-line bg-surface-alt px-3.5 py-2.5 text-sm text-ink">
                    {q}
                  </div>
                ))}
              </div>
              <p className="mt-4 text-xs text-ink-faint">
                Illustrative prompts — the assistant only answers with your real, authenticated account data, never a public demo response.
              </p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* 9. FEATURE GRID */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <Reveal className="mx-auto max-w-xl text-center">
            <h2 className="text-2xl font-extrabold tracking-tight sm:text-3xl">One platform, every layer of the decision.</h2>
          </Reveal>
          <Reveal stagger className="mt-12 grid gap-px overflow-hidden rounded-md border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="lift-on-hover bg-surface p-6">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded border border-ink">
                  <f.icon className="h-4 w-4" />
                </div>
                <h3 className="mb-1 text-sm font-bold">{f.title}</h3>
                <p className="text-sm leading-relaxed text-ink-muted">{f.body}</p>
              </div>
            ))}
          </Reveal>
        </div>
      </section>

      {/* 10. FINAL CTA */}
      <section className="border-t border-line px-6 py-24">
        <Reveal className="mx-auto max-w-6xl rounded-xl bg-ink px-6 py-16 text-center sm:py-20">
          <h2 className="mx-auto max-w-xl text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Your market workspace starts here.
          </h2>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link to="/register" className="rounded bg-white px-6 py-3 text-base font-bold text-ink transition-colors hover:bg-surface-soft">
              Create account
            </Link>
            <Link to="/login" className="rounded border border-white/25 px-6 py-3 text-base font-bold text-white transition-colors hover:border-white/50">
              Sign in
            </Link>
          </div>
        </Reveal>
      </section>

      <footer className="border-t border-line px-6 py-10">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 text-sm text-ink-faint">
          <div>
            <strong className="text-ink">OPTIPORT</strong> · ETF portfolio intelligence, simulated trading, © 2026
          </div>
          <div className="flex flex-wrap gap-5">
            <a href="#ticker" className="transition-colors hover:text-ink">Markets</a>
            <a href="#optimization" className="transition-colors hover:text-ink">Analytics</a>
            <a href="#ai-assistant" className="transition-colors hover:text-ink">AI</a>
            <Link to="/pricing" className="transition-colors hover:text-ink">Pricing</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FlowColumn({
  eyebrow,
  steps,
  result,
  resultLabel,
  tone,
}: {
  eyebrow: string;
  steps: string[];
  result: string;
  resultLabel: string;
  tone: "neutral" | "accent";
}) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-line bg-surface p-6 text-center">
      <span className="text-xs font-bold uppercase tracking-widest text-ink-faint">{eyebrow}</span>
      {steps.map((s, i) => (
        <div key={s} className="contents">
          <div className="mt-4 w-full rounded-md border border-line-soft bg-surface-alt px-3 py-2 text-sm font-medium text-ink">
            {s}
          </div>
          {i < steps.length - 1 && <ArrowIcon className="my-1 h-4 w-4 text-ink-faint" />}
        </div>
      ))}
      <ArrowIcon className="my-2 h-4 w-4 text-ink-faint" />
      <div className={`w-full rounded-md border px-3 py-3 ${tone === "accent" ? "border-accent-strong bg-accent-soft" : "border-line"}`}>
        <p className="font-mono text-2xl font-bold text-up">{result}</p>
        <p className="mt-1 text-xs text-ink-faint">{resultLabel}</p>
      </div>
    </div>
  );
}

function ArrowIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path d="M12 4v14M12 18l-5-5M12 18l5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MarketIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path d="M4 19V9M10 19V5M16 19v-7M22 19v-3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function AnalyticsIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 12 20 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function ForecastIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path d="M3 17l5-6 4 3 5-7 4 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M17 8h4v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function NewsIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <rect x="3.5" y="4.5" width="17" height="15" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M7.5 8.5h9M7.5 12h9M7.5 15.5h5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function TradingIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path d="M4 4v16h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7 15l4-5 3 2 4-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function AssistantIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path d="M4 5.5h16v10H9l-4 3.5v-3.5H4v-10Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <circle cx="9" cy="10.5" r="0.9" fill="currentColor" />
      <circle cx="12" cy="10.5" r="0.9" fill="currentColor" />
      <circle cx="15" cy="10.5" r="0.9" fill="currentColor" />
    </svg>
  );
}
