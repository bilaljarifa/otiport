import type { ReactNode } from "react";
import type { ImpactLevel, SentimentLabel } from "../lib/newsApi";

/** Generic small pill — status/sentiment/impact labels across the app. */
export function Badge({ children, tone }: { children: ReactNode; tone: string }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-semibold ${tone}`}>{children}</span>;
}

export function sentimentTone(label: SentimentLabel): string {
  if (label === "POSITIVE") return "bg-up-soft text-up";
  if (label === "NEGATIVE") return "bg-down-soft text-down";
  return "bg-surface-alt text-ink-muted";
}

export function ImpactBadge({ level, direction }: { level: ImpactLevel; direction: SentimentLabel }) {
  return (
    <Badge tone={sentimentTone(direction)}>
      {direction} impact · {level}
    </Badge>
  );
}
