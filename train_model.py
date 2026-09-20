"""
ETF Forecasting Model Training Script

Trains one LSTM model per ETF ticker to predict 22-day returns. Reuses
`backend/forecaster.py`'s own data-fetching, feature-computation, and model
architecture (`fetch_etf_data`, `compute_features`, `prepare_dataset`,
`build_lstm_model`, `FEATURE_COLS`) so there is no train/serve skew — this
script's only job is to produce artifacts that `forecaster.load_model_with_weights`
and `forecaster.load_scalers` can load exactly as they already expect:

    trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs/
        {TICKER}_model.keras   (one per ticker)
        scalers.pkl            (dict: ticker -> fitted RobustScaler)
"""

from __future__ import annotations

import argparse
import os
import pickle
import random

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.preprocessing import RobustScaler

from backend.forecaster import (
    DEFAULT_MODEL_DIR,
    FEATURE_COLS,
    NUMERIC_FEATURES_INDICES,
    REGION_MAPPING,
    build_lstm_model,
    compute_features,
    fetch_etf_data,
    prepare_dataset,
)

SEED = 42
TICKERS = list(REGION_MAPPING.keys())
START_DATE = "2010-01-01"  # matches forecaster.py's own default fetch window
SEQ_LENGTH = 10  # matches create_sequences_for_prediction's default
EPOCHS = 300
BATCH_SIZE = 16
EARLY_STOP_PATIENCE = 20
MIN_ROWS_REQUIRED = SEQ_LENGTH + 50  # enough rows for a meaningful train/val/test split


def _set_seeds(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    import tensorflow as tf

    tf.random.set_seed(seed)


def create_ticker_sequences(ticker_df: pd.DataFrame, seq_length: int) -> tuple[np.ndarray, np.ndarray]:
    """Sliding windows of `FEATURE_COLS` -> the `return_22d` one row after the window,
    identical in shape/semantics to `forecaster.create_sequences_for_prediction`."""
    features = ticker_df[FEATURE_COLS].values
    target = ticker_df["return_22d"].values
    X, y = [], []
    for i in range(len(features) - seq_length):
        X.append(features[i : i + seq_length])
        y.append(target[i + seq_length])
    if not X:
        return np.empty((0, seq_length, len(FEATURE_COLS))), np.empty((0,))
    return np.array(X), np.array(y)


def train_ticker_model(ticker: str, dataset: pd.DataFrame, models_dir: Path) -> dict:
    ticker_df = dataset[dataset["Ticker"] == ticker].sort_values("Date").reset_index(drop=True)

    if len(ticker_df) < MIN_ROWS_REQUIRED:
        return {
            "ticker": ticker,
            "status": "skipped",
            "reason": f"only {len(ticker_df)} usable rows (need at least {MIN_ROWS_REQUIRED})",
        }

    n = len(ticker_df)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    # Chronological split — no shuffling, no leakage. Val/test windows start
    # `seq_length` rows early so the first sequence in each split doesn't
    # need to reach back across the split boundary.
    train_df = ticker_df.iloc[:train_end].copy()
    val_df = ticker_df.iloc[max(0, train_end - SEQ_LENGTH) : val_end].copy()
    test_df = ticker_df.iloc[max(0, val_end - SEQ_LENGTH) :].copy()

    numeric_cols = [FEATURE_COLS[i] for i in NUMERIC_FEATURES_INDICES]
    scaler = RobustScaler()
    scaler.fit(train_df[numeric_cols].values)

    def _scaled(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out[numeric_cols] = scaler.transform(out[numeric_cols].values)
        return out

    X_train, y_train = create_ticker_sequences(_scaled(train_df), SEQ_LENGTH)
    X_val, y_val = create_ticker_sequences(_scaled(val_df), SEQ_LENGTH)
    X_test, y_test = create_ticker_sequences(_scaled(test_df), SEQ_LENGTH)

    if len(X_train) == 0 or len(X_val) == 0:
        return {
            "ticker": ticker,
            "status": "skipped",
            "reason": "not enough rows left for train/val sequences after the chronological split",
        }

    from tf_keras.callbacks import EarlyStopping

    model = build_lstm_model(input_shape=(SEQ_LENGTH, len(FEATURE_COLS)))
    early_stop = EarlyStopping(monitor="val_loss", patience=EARLY_STOP_PATIENCE, restore_best_weights=True)
    history = model.fit(
        X_train,
        y_train,
        validation_data=(X_val, y_val),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        verbose=0,
        callbacks=[early_stop],
    )

    result: dict = {
        "ticker": ticker,
        "status": "trained",
        "train_rows": int(len(X_train)),
        "val_rows": int(len(X_val)),
        "epochs_run": len(history.history["loss"]),
        "final_val_loss": float(history.history["val_loss"][-1]),
    }

    if len(X_test) > 0:
        test_loss, test_mae = model.evaluate(X_test, y_test, verbose=0)
        result["test_rows"] = int(len(X_test))
        result["test_loss"] = float(test_loss)
        result["test_mae"] = float(test_mae)
    else:
        result["test_rows"] = 0

    model_path = models_dir / f"{ticker}_model.keras"
    model.save(str(model_path))
    result["model_path"] = str(model_path)
    result["_scaler"] = scaler  # stripped by the caller before printing/summarizing
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=TICKERS,
        help="Subset of tickers to train (default: all 12 configured ETFs).",
    )
    args = parser.parse_args()
    tickers = args.tickers

    _set_seeds()

    models_dir = Path(DEFAULT_MODEL_DIR)
    models_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching data for {len(tickers)} ticker(s) since {START_DATE}: {tickers}")
    close_prices = fetch_etf_data(tickers, START_DATE)
    print(f"Fetched {len(close_prices)} rows of price history.")

    print("Computing features (backend.forecaster.compute_features — same as inference)...")
    features = compute_features(close_prices)
    dataset = prepare_dataset(features, tickers)
    dataset = dataset.sort_values(["Ticker", "Date"])

    # Merge with any scalers already saved for tickers not in this run, so a
    # partial/subset run never destroys previously trained tickers' scalers.
    scalers_path = models_dir / "scalers.pkl"
    if scalers_path.exists():
        with open(scalers_path, "rb") as f:
            scalers: dict = pickle.load(f)
    else:
        scalers = {}

    summary = []
    for ticker in tickers:
        print(f"\n=== Training {ticker} ===")
        result = train_ticker_model(ticker, dataset, models_dir)
        if result["status"] == "trained":
            scalers[ticker] = result.pop("_scaler")
        print({k: v for k, v in result.items() if k != "_scaler"})
        summary.append(result)

    with open(scalers_path, "wb") as f:
        pickle.dump(scalers, f)
    print(f"\nSaved per-ticker scalers ({len(scalers)} total) to {scalers_path}")

    trained = [s for s in summary if s["status"] == "trained"]
    skipped = [s for s in summary if s["status"] != "trained"]
    print(f"\nTrained {len(trained)}/{len(tickers)} model(s) this run.")
    if skipped:
        print("Skipped:")
        for s in skipped:
            print(f"  - {s['ticker']}: {s['reason']}")


if __name__ == "__main__":
    main()
