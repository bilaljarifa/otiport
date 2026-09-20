/**
 * The app's own ETF universe (mirrors `ETF_METADATA` in api.py) plus the two
 * major benchmarks used elsewhere on the Dashboard — a fixed, honestly
 * labeled quick-select list, not a claim of "all tradable tickers." Shared
 * between Markets and Trading so the two quick-select lists can't drift.
 */
export interface EtfMeta {
  ticker: string;
  name: string;
  region: string;
  /** Has a trained LSTM model (the 12 sector ETFs) vs. a broad-market
   * benchmark (SPY/QQQ) shown for context but never forecast. */
  hasModel: boolean;
}

export const ETF_UNIVERSE: EtfMeta[] = [
  { ticker: "SPY", name: "S&P 500", region: "Broad Market", hasModel: false },
  { ticker: "QQQ", name: "Nasdaq 100", region: "Broad Market", hasModel: false },
  { ticker: "PSI", name: "Semiconductors", region: "North America", hasModel: true },
  { ticker: "IYW", name: "US Technology", region: "North America", hasModel: true },
  { ticker: "RING", name: "Gold Miners", region: "Developed Markets", hasModel: true },
  { ticker: "PICK", name: "Metals & Mining", region: "Developed Markets", hasModel: true },
  { ticker: "NLR", name: "Nuclear Energy", region: "Developed Markets", hasModel: true },
  { ticker: "UTES", name: "Utilities", region: "North America", hasModel: true },
  { ticker: "LIT", name: "Lithium & Battery", region: "Developed Markets", hasModel: true },
  { ticker: "NANR", name: "Natural Resources", region: "North America", hasModel: true },
  { ticker: "GUNR", name: "Global Resources", region: "Developed Markets", hasModel: true },
  { ticker: "XCEM", name: "Emerging Markets", region: "Emerging Markets", hasModel: true },
  { ticker: "PTLC", name: "Large Cap", region: "North America", hasModel: true },
  { ticker: "FXU", name: "Utilities Alpha", region: "North America", hasModel: true },
];

export const TICKER_PATTERN = /^[A-Z]{1,6}$/;
