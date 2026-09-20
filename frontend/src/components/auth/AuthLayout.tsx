import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Brand } from "../Brand";
import { ThemeToggle } from "../ThemeToggle";
import { LiveMarketPreview } from "./LiveMarketPreview";

const CAPABILITIES = [
  "Real ETF market data",
  "LSTM forecasting + news context",
  "Portfolio optimization",
  "Paper trading & analytics",
];

/**
 * Purely decorative — a restrained grid + one abstract ascending line, never
 * real ticker data. `text-accent` picks up the theme's own blue token so
 * this never introduces a new color.
 */
function AuthBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div
        className="absolute inset-0 opacity-[0.05]"
        style={{
          backgroundImage:
            "linear-gradient(var(--color-line) 1px, transparent 1px), linear-gradient(90deg, var(--color-line) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
        }}
      />
      <svg
        className="absolute inset-x-0 bottom-0 h-40 w-full text-accent opacity-[0.16]"
        viewBox="0 0 400 160"
        preserveAspectRatio="none"
        fill="none"
      >
        <path
          d="M-10 130 L30 118 L60 128 L95 88 L130 102 L165 62 L200 78 L235 42 L270 60 L310 24 L410 46"
          stroke="currentColor"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
        {[[30, 118], [95, 88], [165, 62], [235, 42], [310, 24]].map(([cx, cy]) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.5" fill="currentColor" />
        ))}
      </svg>
    </div>
  );
}

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen bg-surface">
      <div className="absolute right-4 top-4 z-20 md:right-6 md:top-6">
        <ThemeToggle />
      </div>

      {/* Branding panel — hidden below `md`; the mobile experience gets a
          compact header instead (see below), never a squeezed two-column
          layout. `md:sticky md:h-screen` pins it to exactly the viewport
          height regardless of how tall the form panel is (Register's form
          is much taller than Login's) — without this, the panel used to
          stretch to match the taller sibling and `justify-between` spread
          its few content blocks across all that extra height, leaving
          large, unbalanced empty gaps. Deliberately no `overflow-y-auto`
          here even though a very short viewport could in theory clip this
          panel's content — adding any `overflow` property to an ancestor
          of `LiveMarketPreview`'s `.hero-enter` animation reproduced the
          exact paint bug described below (the card's real quotes rendered
          permanently washed out at some viewport widths), so panel content
          is kept compact enough to fit typical viewport heights instead. */}
      <div className="relative hidden w-[42%] shrink-0 flex-col justify-between border-r border-line px-8 py-10 md:sticky md:top-0 md:flex md:h-screen md:px-10 lg:px-12 lg:py-12 xl:w-[38%]">
        {/* Deliberately static (no `.hero-enter`) — this panel's own text
            proved unreliable to paint on this Chrome build whenever a
            CSS `animation` and `overflow-hidden` both sat in its ancestor
            chain (compositor-layer quirk: computed style was always
            correct, but the text intermittently never painted). The form
            panel below still animates in — that side never showed the
            issue — so motion is kept where it's provably safe rather than
            chasing a flaky bug for a purely decorative entrance. */}
        <AuthBackdrop />
        <Link to="/" className="relative z-10 w-fit">
          <Brand size="lg" />
        </Link>
        <div className="relative z-10 flex max-w-md flex-col gap-5">
          <div>
            <h1 className="text-2xl font-bold leading-[1.15] tracking-tight text-ink lg:text-4xl">
              Understand the market.
              <br />
              Build with confidence.
            </h1>
            <p className="mt-3 text-sm leading-relaxed text-ink-muted lg:text-base">
              Market intelligence, portfolio optimization, forecasting and paper trading in one
              workspace.
            </p>
          </div>

          <LiveMarketPreview />

          <div className="grid grid-cols-2 gap-x-4 gap-y-2.5">
            {CAPABILITIES.map((c) => (
              <div key={c} className="flex items-center gap-2 text-xs text-ink-muted lg:text-sm">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden="true" />
                {c}
              </div>
            ))}
          </div>
        </div>
        <p className="relative z-10 text-xs text-ink-faint">
          Simulated paper-trading account — no real funds or brokerage involved.
        </p>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12 sm:px-10">
        <Link to="/" className="mb-8 flex justify-center md:hidden">
          <Brand size="md" />
        </Link>

        <div className="hero-enter w-full max-w-sm">
          <h2 className="text-2xl font-bold tracking-tight text-ink">{title}</h2>
          <p className="mt-1.5 text-sm text-ink-muted">{subtitle}</p>
          <div className="mt-6">{children}</div>
          <div className="mt-6">{footer}</div>
        </div>
      </div>
    </div>
  );
}
