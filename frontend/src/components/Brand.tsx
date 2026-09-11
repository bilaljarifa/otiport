/**
 * Optiport's mark: three ascending bars inside a square frame — the same
 * symbol used across the Streamlit app (`ui/assets/logo*.svg`,
 * `ui.components.brand_mark_html`), reimplemented natively here rather than
 * embedding an image, so it can be recolored per surface (dark sidebar vs.
 * light page) without shipping two asset files.
 */
export function Mark({ size = 28, color = "currentColor" }: { size?: number; color?: string }) {
  const bar = (heightPct: number, key: string) => (
    <span
      key={key}
      style={{ width: "18%", height: `${heightPct}%`, background: color }}
      className="inline-block"
    />
  );
  return (
    <span
      style={{
        width: size,
        height: size,
        border: `1.5px solid ${color}`,
      }}
      className="box-border inline-flex shrink-0 items-end justify-center gap-[2px] rounded p-[3px]"
    >
      {bar(35, "s")}
      {bar(60, "m")}
      {bar(90, "l")}
    </span>
  );
}

export function Brand({
  size = "md",
  color = "currentColor",
}: {
  size?: "sm" | "md" | "lg";
  color?: string;
}) {
  const markSize = { sm: 22, md: 28, lg: 36 }[size];
  const textSize = { sm: "text-sm", md: "text-lg", lg: "text-2xl" }[size];
  return (
    <span className="inline-flex items-center gap-2.5">
      <Mark size={markSize} color={color} />
      <span className={`font-extrabold tracking-wide ${textSize}`} style={{ color }}>
        OPTIPORT
      </span>
    </span>
  );
}
