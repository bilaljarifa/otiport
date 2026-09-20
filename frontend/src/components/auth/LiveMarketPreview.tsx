import { usePublicMarketTicker } from "../../lib/queries";
import { ETF_UNIVERSE } from "../../lib/catalog";

/** The fixed, small set of tickers shown on the auth pages — a preview, not
 * the full public ticker tape. Real quotes only: a ticker missing from the
 * response is simply left out, never shown with a made-up price. */
const PREVIEW_TICKERS = ["SPY", "QQQ", "PSI", "IYW"];

const TICKER_NAMES = new Map(ETF_UNIVERSE.map((e) => [e.ticker, e.name]));

function ChangeTag({ value }: { value: number }) {
  const tone = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-ink-faint";
  return (
    <span className={`font-mono text-xs font-bold ${tone}`}>
      {value > 0 ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}

function MarketStatus({ state }: { state: "loading" | "live" | "unavailable" }) {
  if (state === "loading") {
    return <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Connecting…</span>;
  }
  if (state === "unavailable") {
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
        <span className="h-1.5 w-1.5 rounded-full bg-ink-faint" aria-hidden="true" />
        Market data unavailable
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-up">
      <span className="status-pulse h-1.5 w-1.5 rounded-full bg-up" aria-hidden="true" />
      Market data live
    </span>
  );
}

function MarketTickerRow({
  ticker,
  price,
  changePct,
}: {
  ticker: string;
  price: number;
  changePct: number;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="flex min-w-0 items-baseline gap-2">
        <span className="font-mono text-sm font-bold text-ink">{ticker}</span>
        <span className="truncate text-xs text-ink-faint">{TICKER_NAMES.get(ticker) ?? ""}</span>
      </span>
      <span className="flex shrink-0 items-baseline gap-2.5">
        <span className="font-mono text-sm font-semibold text-ink">${price.toFixed(2)}</span>
        <ChangeTag value={changePct} />
      </span>
    </div>
  );
}

/**
 * Compact, real-data market preview for the auth pages' brand panel. Reuses
 * the exact same `GET /public/market/quotes` query the Landing page ticker
 * already uses (`usePublicMarketTicker`, shared cache — no extra request),
 * so authentication never depends on a second market-data endpoint and
 * never adds a request beyond what the app already makes elsewhere.
 *
 * The login/register form itself never depends on this: a failed or slow
 * quote fetch only changes what renders in this panel, never the form.
 */
export function LiveMarketPreview() {
  const ticker = usePublicMarketTicker();

  if (ticker.isLoading) {
    return (
      <div className="rounded-md border border-line px-4 py-3">
        <MarketStatus state="loading" />
        <div className="mt-2 flex flex-col gap-2">
          {PREVIEW_TICKERS.map((t) => (
            <div key={t} className="h-5 w-full animate-pulse rounded bg-surface-alt" />
          ))}
        </div>
      </div>
    );
  }

  const quotes = ticker.data?.quotes ?? {};
  const rows = PREVIEW_TICKERS.map((t) => quotes[t]).filter((q): q is NonNullable<typeof q> => Boolean(q));

  if (ticker.isError || rows.length === 0) {
    return (
      <div className="rounded-md border border-line px-4 py-3">
        <MarketStatus state="unavailable" />
        <p className="mt-2 text-xs text-ink-faint">
          Live quotes are temporarily unavailable. This never affects signing in.
        </p>
      </div>
    );
  }

  return (
    // No `.hero-enter` here on purpose — this card lives inside the auth
    // pages' `md:sticky` branding panel, and pairing a CSS animation with a
    // sticky/compositing-layer-promoted ancestor reproduced the same
    // intermittent "computed style is right but the pixels never repaint"
    // Chrome quirk documented on that panel itself (see AuthLayout.tsx).
    // Reliability wins over a fade-in on a card that's mostly numbers.
    <div className="rounded-md border border-line px-4 py-3">
      <MarketStatus state="live" />
      <div className="mt-1.5 divide-y divide-line-soft">
        {rows.map((q) => (
          <MarketTickerRow key={q.ticker} ticker={q.ticker} price={q.price} changePct={q.change_pct} />
        ))}
      </div>
    </div>
  );
}
