/**
 * The one place every button's color/border/hover behavior is defined.
 * Three variants, used everywhere — no page invents its own button colors.
 *
 * primary:   white bg, black border, black text  -> hover: black bg, white text
 * secondary: white bg, light-gray border, gray text -> hover: darker border, black text
 * accent:    restrained blue — only for actions that genuinely need an accent
 *            (never the default choice for navigation/auth buttons)
 */
export const buttonVariants = {
  primary: "border border-ink bg-surface text-ink hover:bg-ink hover:text-white",
  secondary: "border border-line-strong bg-surface text-ink-muted hover:border-ink hover:text-ink",
  accent:
    "border border-accent-strong bg-accent-strong text-white hover:bg-accent-strong-hover hover:border-accent-strong-hover",
} as const;

export type ButtonVariant = keyof typeof buttonVariants;

const BASE =
  "inline-flex items-center justify-center gap-2 rounded px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50";

export function buttonClass(variant: ButtonVariant = "primary", extra = ""): string {
  return `${BASE} ${buttonVariants[variant]} ${extra}`.trim();
}
