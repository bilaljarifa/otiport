export function money(value: number, decimals = 0): string {
  const sign = value < 0 ? "-" : "";
  return `${sign}$${Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

export function signedMoney(value: number, decimals = 0): string {
  const sign = value >= 0 ? "+" : "-";
  return `${sign}${money(Math.abs(value), decimals)}`;
}

export function percent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

export function signedPercent(value: number, decimals = 2): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}
