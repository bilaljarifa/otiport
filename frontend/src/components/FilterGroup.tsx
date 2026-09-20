/**
 * Segmented control — dark/near-black selected state with a subtle accent
 * border, transparent unselected state. Originally the Admin user-table
 * status/role filters; shared here so the same control (and the same
 * dark-mode fix for `--color-ink` flipping in light mode — see
 * `--color-ink-strong`) isn't redefined per page.
 */
export function FilterGroup<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string; disabled?: boolean; title?: string }[];
}) {
  return (
    <div className="inline-flex h-8 shrink-0 items-center gap-0.5 rounded-md border border-line-strong bg-surface p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          disabled={opt.disabled}
          title={opt.title}
          onClick={() => onChange(opt.value)}
          className={`inline-flex h-full items-center whitespace-nowrap rounded border px-2.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-strong/40 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent ${
            value === opt.value
              ? "border-accent-strong bg-ink-strong text-white"
              : "border-transparent text-ink-muted hover:bg-surface-alt hover:text-ink"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
