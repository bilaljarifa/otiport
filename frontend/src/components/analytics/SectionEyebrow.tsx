import type { ReactNode } from "react";

/** Small eyebrow label above a section — the "Configuration / Results /
 * Visual Analytics / Methodology" structure every analytics panel shares. */
export function SectionEyebrow({ children }: { children: ReactNode }) {
  return <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">{children}</div>;
}
