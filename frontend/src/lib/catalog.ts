/**
 * The app's own ETF universe (mirrors `ETF_METADATA` in api.py) plus the two
 * major benchmarks used elsewhere on the Dashboard — a fixed, honestly
 * labeled quick-select list, not a claim of "all tradable tickers." Shared
 * between Markets and Trading so the two quick-select lists can't drift.
 */
export interface EtfMeta {
  ticker: string;
  name: string;
}

export const ETF_UNIVERSE: EtfMeta[] = [
  { ticker: "SPY", name: "S&P 500" },
  { ticker: "QQQ", name: "Nasdaq 100" },
  { ticker: "PSI", name: "Semiconductors" },
  { ticker: "IYW", name: "US Technology" },
  { ticker: "RING", name: "Gold Miners" },
  { ticker: "PICK", name: "Metals & Mining" },
  { ticker: "NLR", name: "Nuclear Energy" },
  { ticker: "UTES", name: "Utilities" },
  { ticker: "LIT", name: "Lithium & Battery" },
  { ticker: "NANR", name: "Natural Resources" },
  { ticker: "GUNR", name: "Global Resources" },
  { ticker: "XCEM", name: "Emerging Markets" },
  { ticker: "PTLC", name: "Large Cap" },
  { ticker: "FXU", name: "Utilities Alpha" },
];

export const TICKER_PATTERN = /^[A-Z]{1,6}$/;
