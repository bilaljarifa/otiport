export function StatTile({
  label,
  value,
  delta,
  hint,
}: {
  label: string;
  value: string;
  delta?: { value: string; positive: boolean } | null;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-line p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">{label}</div>
      <div className="mt-1.5 font-mono text-xl font-bold text-ink">{value}</div>
      <div className="mt-1 flex items-center gap-2 text-xs">
        {delta && (
          <span className={`font-mono font-semibold ${delta.positive ? "text-up" : "text-down"}`}>
            {delta.value}
          </span>
        )}
        {hint && <span className="text-ink-faint">{hint}</span>}
      </div>
    </div>
  );
}
