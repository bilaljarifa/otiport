import numpy as np
import pandas as pd
import yfinance as yf
import pickle
import zipfile
import tempfile
import h5py
from sklearn.preprocessing import RobustScaler, LabelEncoder
from typing import List, Dict, Tuple, Optional
from pathlib import Path

from backend.market_cache import cache_key, price_history_cache

# Region mapping for ETFs
REGION_MAPPING = {
    "PSI": "North America",
    "IYW": "North America",
    "RING": "Developed Markets",
    "PICK": "Developed Markets",
    "NLR": "Developed Markets",
    "UTES": "North America",
    "LIT": "Developed Markets",
    "NANR": "North America",
    "GUNR": "Developed Markets",
    "XCEM": "Emerging Markets",
    "PTLC": "North America",
    "FXU": "North America",
}

# Default region for unknown tickers
DEFAULT_REGION = "North America"

# Default model directory
DEFAULT_MODEL_DIR = "trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs"

# Feature columns used by the model (must match training)
FEATURE_COLS = ['corr_3m', 'max_dd_6m', 'momentum_1m', 'momentum_3m', 'momentum_6m', 'vol_1m', 'Region_Encoded', 'rsi_14', 'position_52w']

# Numeric features for scaling (excludes Region_Encoded which is at index 6)
NUMERIC_FEATURES_INDICES = [0, 1, 2, 3, 4, 5, 7, 8]


def build_lstm_model(input_shape=(10, 9)):
    """Build LSTM model with same architecture as training."""
    from tf_keras.models import Sequential
    from tf_keras.layers import LSTM, Dense, Dropout
    from tf_keras.regularizers import l2

    model = Sequential([
        LSTM(16, input_shape=input_shape, kernel_regularizer=l2(0.0001)),
        Dropout(0.2),
        Dense(1, kernel_regularizer=l2(0.0001))
    ])
    model.compile(optimizer='adam', loss='huber', metrics=['mae'])
    return model


def load_model_with_weights(model_path: str):
    """
    Load model by manually extracting weights from .keras file.
    This handles compatibility issues between Keras versions.
    """
    model = build_lstm_model(input_shape=(10, 9))

    with zipfile.ZipFile(model_path, 'r') as z:
        with tempfile.TemporaryDirectory() as tmpdir:
            z.extractall(tmpdir)
            weights_path = Path(tmpdir) / 'model.weights.h5'

            with h5py.File(weights_path, 'r') as f:
                # Load LSTM weights
                lstm_kernel = np.array(f['layers/lstm/cell/vars/0'])
                lstm_recurrent = np.array(f['layers/lstm/cell/vars/1'])
                lstm_bias = np.array(f['layers/lstm/cell/vars/2'])

                # Load Dense weights
                dense_kernel = np.array(f['layers/dense/vars/0'])
                dense_bias = np.array(f['layers/dense/vars/1'])

                # Set weights (layers[0]=LSTM, layers[1]=Dropout, layers[2]=Dense)
                model.layers[0].set_weights([lstm_kernel, lstm_recurrent, lstm_bias])
                model.layers[2].set_weights([dense_kernel, dense_bias])

    return model


def fetch_etf_data(tickers: List[str], start_date: str = "2010-01-01") -> pd.DataFrame:
    """Fetch close prices for given tickers from Yahoo Finance.

    Cached for a short TTL (`backend/market_cache.py`) keyed by the exact
    (tickers, start_date) pair — this is the single most expensive call in
    the forecasting/optimization path (full history for every ticker), and
    it's requested with identical arguments very often: `get_portfolio_data`
    used to call it twice per request for this exact reason, and repeat
    `/forecast`/`/smart-invest`/`/efficient-frontier` calls for the same
    universe (a slider tweak, a second user, a page revisit) are common.
    Returns a copy on a cache hit so callers can never mutate the cached frame.
    """
    key = cache_key("fetch_etf_data", sorted(tickers), start_date)
    cached = price_history_cache.get(key)
    if cached is not None:
        return cached.copy()

    result = _fetch_etf_data_uncached(tickers, start_date)
    price_history_cache.set(key, result.copy())
    return result


def _fetch_etf_data_uncached(tickers: List[str], start_date: str = "2010-01-01") -> pd.DataFrame:
    try:
        data = yf.download(tickers=tickers, start=start_date, auto_adjust=True, progress=False)

        if data.empty:
            raise ValueError(f"No data returned for tickers: {tickers}")

        # Extract Close prices
        if isinstance(data.columns, pd.MultiIndex):
            close_prices = data['Close'].copy()
            if hasattr(close_prices.columns, 'name'):
                close_prices.columns.name = None
        else:
            if len(tickers) == 1:
                close_prices = data[['Close']].copy()
                close_prices.columns = tickers
            else:
                close_prices = data['Close'].copy()

        if isinstance(close_prices, pd.Series):
            close_prices = close_prices.to_frame(name=tickers[0])

        close_prices = close_prices.dropna()

        # A partial or throttled download can yield rows that share no common
        # dates across tickers. Without this guard the emptiness only surfaces
        # much later as an opaque pandas error during feature preparation.
        if close_prices.empty:
            raise ValueError(
                "no overlapping price history across the requested tickers "
                "(the data provider may have returned an incomplete response)"
            )

        return close_prices

    except Exception as e:
        raise ValueError(f"Error fetching data for tickers {tickers}: {str(e)}")


def compute_rsi(prices: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """Compute RSI indicator."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
    rs = gain / (loss + 1e-8)
    return 100 - (100 / (1 + rs))


def compute_features(close_prices: pd.DataFrame) -> pd.DataFrame:
    """Compute technical features from close prices (matches notebook approach)."""
    returns = close_prices.pct_change().dropna()

    # Momentum features
    momentum_1m = close_prices.pct_change(21)
    momentum_3m = close_prices.pct_change(63)
    momentum_6m = close_prices.pct_change(126)

    # Volatility features
    vol_1m = returns.rolling(21).std()

    # 22-day return (target variable for training, feature for context)
    return_22d = close_prices.pct_change(22)

    # Max drawdown over each trailing 126-day window. Vectorized with numpy
    # instead of `rolling(126).apply(python_fn, raw=False)` — the original
    # called a Python-level function per column per row (~32k times for a
    # 12-ticker/2010-present fetch), measured at ~9s of the ~10-16s this
    # endpoint took; this produces bit-identical output (verified: max abs
    # diff 0.0 against the rolling().apply() version) in ~0.05s.
    def _rolling_drawdown(arr: np.ndarray, window: int) -> np.ndarray:
        n = len(arr)
        out = np.full(n, np.nan)
        if n < window:
            return out
        windows = np.lib.stride_tricks.sliding_window_view(arr, window)
        cumulative = np.cumprod(1 + windows, axis=1)
        peak = np.maximum.accumulate(cumulative, axis=1)
        drawdown = (cumulative - peak) / peak
        out[window - 1:] = drawdown.min(axis=1)
        return out

    drawdown_6m = pd.DataFrame(
        {col: _rolling_drawdown(returns[col].to_numpy(), 126) for col in returns.columns},
        index=returns.index,
    )

    # Correlation features
    corr_3m = returns.rolling(63).corr().groupby(level=0).mean()

    # RSI indicator
    rsi_14 = compute_rsi(close_prices, 14)

    # Position in 52-week range (0 = lowest, 1 = highest)
    high_52w = close_prices.rolling(252).max()
    low_52w = close_prices.rolling(252).min()
    position_52w = (close_prices - low_52w) / (high_52w - low_52w + 1e-8)

    # Combine features
    features = pd.concat({
        "return_22d": return_22d,
        "momentum_1m": momentum_1m,
        "momentum_3m": momentum_3m,
        "momentum_6m": momentum_6m,
        "vol_1m": vol_1m,
        "max_dd_6m": drawdown_6m,
        "corr_3m": corr_3m,
        "rsi_14": rsi_14,
        "position_52w": position_52w
    }, axis=1).dropna()

    return features


def prepare_dataset(features: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    """Prepare dataset in the format expected by the model."""
    # Features need ~252 sessions of history before the rolling windows produce
    # a single complete row; report that explicitly rather than letting the
    # reshape below fail with "Columns must be same length as key".
    if features.empty:
        raise ValueError(
            "not enough price history to compute model features for "
            f"{', '.join(tickers)} (at least 252 trading sessions are required)"
        )

    # Flatten column names
    features.columns = [f"{feat}_{ticker}" for feat, ticker in features.columns]

    # Reshape to long format
    dataset = features.reset_index()
    dataset = dataset.melt(id_vars="Date", var_name="Ticker_Feature", value_name="value")
    dataset[["Feature", "Ticker"]] = dataset["Ticker_Feature"].str.rsplit("_", n=1, expand=True)
    dataset = dataset.pivot_table(index=["Date", "Ticker"], columns="Feature", values="value").reset_index()
    dataset = dataset.dropna().reset_index(drop=True)

    # Add region encoding
    le = LabelEncoder()
    le.fit(["Developed Markets", "Emerging Markets", "North America"])
    dataset["Region"] = dataset["Ticker"].map(lambda t: REGION_MAPPING.get(t, DEFAULT_REGION))
    dataset['Region_Encoded'] = le.transform(dataset['Region'])

    return dataset


def load_scalers(model_dir: str) -> Dict[str, RobustScaler]:
    """Load per-ticker scalers from pickle file."""
    scalers_path = Path(model_dir) / "scalers.pkl"
    if scalers_path.exists():
        with open(scalers_path, 'rb') as f:
            return pickle.load(f)
    return {}


def create_sequences_for_prediction(
    data: pd.DataFrame,
    ticker: str,
    scaler: Optional[RobustScaler] = None,
    seq_length: int = 10
) -> Tuple[np.ndarray, Dict]:
    """Create sequences for a single ticker's prediction."""
    ticker_data = data[data['Ticker'] == ticker].sort_values('Date')

    if len(ticker_data) < seq_length:
        return None, None

    features = ticker_data[FEATURE_COLS].values.copy()
    dates = ticker_data['Date'].values
    last_return_22d = ticker_data['return_22d'].values[-1] if 'return_22d' in ticker_data.columns else 0.0

    # Apply scaling if scaler provided
    if scaler is not None:
        features_flat = features.reshape(-1, features.shape[1])
        features_flat[:, NUMERIC_FEATURES_INDICES] = scaler.transform(features_flat[:, NUMERIC_FEATURES_INDICES])
        features = features_flat

    # Get the last sequence for prediction
    X = features[-seq_length:].reshape(1, seq_length, len(FEATURE_COLS))

    info = {
        'ticker': ticker,
        'date': dates[-1],
        'last_return_22d': last_return_22d
    }

    return X, info


def predict_returns(
    tickers: List[str],
    model_path: Optional[str] = None,
    start_date: str = "2010-01-01",
    close_prices: Optional[pd.DataFrame] = None,
) -> Dict[str, Dict]:
    """
    Predict 22-day returns for given tickers using per-ticker LSTM models.

    Args:
        tickers: List of ETF ticker symbols
        model_path: Path to model directory containing per-ticker models
        start_date: Start date for historical data
        close_prices: Already-fetched close prices for `tickers`/`start_date`
            (as returned by `fetch_etf_data`) to reuse instead of fetching
            again — used by `get_portfolio_data` so the same Yahoo Finance
            download backs both the forecast and the covariance matrix.
            When omitted, fetched exactly as before.

    Returns:
        Dictionary with ticker predictions and metadata
    """
    # Determine model directory
    if model_path:
        model_dir = Path(model_path).parent if model_path.endswith('.keras') else Path(model_path)
    else:
        model_dir = Path(DEFAULT_MODEL_DIR)

    # Fetch and prepare data
    if close_prices is None:
        close_prices = fetch_etf_data(tickers, start_date)
    features = compute_features(close_prices)
    dataset = prepare_dataset(features, tickers)

    # Sort by ticker and date
    dataset = dataset.sort_values(['Ticker', 'Date'])

    # Load scalers
    scalers = load_scalers(str(model_dir))

    predictions = {}

    # Check if models exist
    models_available = model_dir.exists() and any(model_dir.glob("*_model.keras"))

    if models_available:
        try:
            for ticker in tickers:
                model_file = model_dir / f"{ticker}_model.keras"

                if not model_file.exists():
                    predictions[ticker] = {
                        'predicted_return_22d': None,
                        'last_actual_return_22d': 0.0,
                        'prediction_date': str(dataset[dataset['Ticker'] == ticker]['Date'].max())[:10] if len(dataset[dataset['Ticker'] == ticker]) > 0 else 'N/A',
                        'note': f'Model not found for {ticker}'
                    }
                    continue

                # Get scaler for this ticker
                scaler = scalers.get(ticker)

                # Create sequence for prediction
                X, info = create_sequences_for_prediction(dataset, ticker, scaler, seq_length=10)

                if X is None:
                    predictions[ticker] = {
                        'predicted_return_22d': None,
                        'last_actual_return_22d': 0.0,
                        'prediction_date': 'N/A',
                        'note': f'Insufficient data for {ticker}'
                    }
                    continue

                # Load model using custom loader for Keras version compatibility
                model = load_model_with_weights(str(model_file))
                y_pred = model.predict(X, verbose=0)

                predictions[ticker] = {
                    'predicted_return_22d': float(y_pred[0][0]),
                    'last_actual_return_22d': float(info['last_return_22d']),
                    'prediction_date': str(info['date'])[:10]
                }

        except Exception as e:
            # Fallback if models can't be loaded
            for ticker in tickers:
                ticker_data = dataset[dataset['Ticker'] == ticker]
                if len(ticker_data) > 0:
                    predictions[ticker] = {
                        'predicted_return_22d': None,
                        'last_actual_return_22d': float(ticker_data['return_22d'].values[-1]) if 'return_22d' in ticker_data.columns else 0.0,
                        'prediction_date': str(ticker_data['Date'].values[-1])[:10],
                        'note': f'Error loading model: {str(e)}'
                    }
                else:
                    predictions[ticker] = {
                        'predicted_return_22d': None,
                        'last_actual_return_22d': 0.0,
                        'prediction_date': 'N/A',
                        'note': 'No data available'
                    }
    else:
        # No models available - return historical data only
        for ticker in tickers:
            ticker_data = dataset[dataset['Ticker'] == ticker]
            if len(ticker_data) > 0:
                predictions[ticker] = {
                    'predicted_return_22d': None,
                    'last_actual_return_22d': float(ticker_data['return_22d'].values[-1]) if 'return_22d' in ticker_data.columns else 0.0,
                    'prediction_date': str(ticker_data['Date'].values[-1])[:10],
                    'note': 'Model not loaded - returning historical data only'
                }
            else:
                predictions[ticker] = {
                    'predicted_return_22d': None,
                    'last_actual_return_22d': 0.0,
                    'prediction_date': 'N/A',
                    'note': 'No data available'
                }

    return predictions


def get_expected_returns(
    tickers: List[str],
    model_path: Optional[str] = None,
    start_date: str = "2010-01-01",
    close_prices: Optional[pd.DataFrame] = None,
) -> np.ndarray:
    """
    Get expected returns vector for portfolio optimization.

    Returns annualized expected returns based on 22-day predictions.

    `close_prices`, when given, is reused instead of fetched again — see
    `predict_returns`.
    """
    predictions = predict_returns(tickers, model_path, start_date, close_prices=close_prices)

    mu = []
    for ticker in tickers:
        if ticker in predictions:
            pred = predictions[ticker].get('predicted_return_22d')
            if pred is not None:
                # Annualize 22-day return (approximately 12 periods per year)
                annualized = (1 + pred) ** 12 - 1
                mu.append(annualized)
            else:
                # Fallback to historical return
                hist = predictions[ticker].get('last_actual_return_22d', 0.0)
                annualized = (1 + hist) ** 12 - 1
                mu.append(annualized)
        else:
            mu.append(0.0)

    return np.array(mu)


def compute_covariance_matrix(
    tickers: List[str],
    start_date: str = "2010-01-01",
    annualize: bool = True,
    close_prices: Optional[pd.DataFrame] = None,
) -> Tuple[np.ndarray, pd.DataFrame]:
    """
    Compute historical covariance matrix for given tickers.

    Args:
        tickers: List of ticker symbols
        start_date: Start date for historical data
        annualize: Whether to annualize the covariance matrix
        close_prices: Already-fetched close prices to reuse instead of
            fetching again — see `predict_returns`.

    Returns:
        Tuple of (covariance matrix as numpy array, returns DataFrame)
    """
    if close_prices is None:
        close_prices = fetch_etf_data(tickers, start_date)
    returns = close_prices.pct_change().dropna()

    cov_matrix = returns.cov()

    if annualize:
        # Annualize covariance (252 trading days)
        cov_matrix = cov_matrix * 252

    # Ensure tickers are in correct order
    cov_matrix = cov_matrix.reindex(index=tickers, columns=tickers)

    return cov_matrix.values, returns


def get_portfolio_data(
    tickers: List[str],
    model_path: Optional[str] = None,
    start_date: str = "2010-01-01"
) -> Dict:
    """
    Get all data needed for portfolio optimization.

    Args:
        tickers: List of ETF ticker symbols
        model_path: Path to trained model directory
        start_date: Start date for historical data

    Returns:
        Dictionary with expected returns, covariance matrix, and metadata
    """
    # Fetch once, shared by both the forecast and the covariance matrix below
    # — they previously fetched the identical (tickers, start_date) history
    # independently, doubling the slowest step in this function for no
    # difference in the result (same data, same values either way).
    close_prices = fetch_etf_data(tickers, start_date)

    # Get forecasted expected returns
    mu = get_expected_returns(tickers, model_path, start_date, close_prices=close_prices)

    # Cap extreme returns to reasonable values (max 200% annual)
    mu = np.clip(mu, -0.5, 2.0)

    # Replace NaN with 0
    mu = np.nan_to_num(mu, nan=0.0)

    # Get covariance matrix
    cov, returns = compute_covariance_matrix(tickers, start_date, close_prices=close_prices)

    # Handle NaN in covariance matrix
    cov = np.nan_to_num(cov, nan=0.0)

    # Ensure covariance matrix is positive semi-definite
    min_eig = np.min(np.linalg.eigvalsh(cov))
    if min_eig < 0:
        cov = cov + (-min_eig + 1e-6) * np.eye(len(tickers))

    # Get historical statistics
    hist_returns = returns.mean() * 252  # Annualized
    hist_volatility = returns.std() * np.sqrt(252)  # Annualized

    # Replace NaN in historical stats
    hist_returns = hist_returns.fillna(0.0)
    hist_volatility = hist_volatility.fillna(0.0)

    return {
        "tickers": tickers,
        "expected_returns": mu,
        "covariance_matrix": cov,
        "historical_returns": hist_returns.to_dict(),
        "historical_volatility": hist_volatility.to_dict()
    }
