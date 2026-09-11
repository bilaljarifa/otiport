from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Literal
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import APP_VERSION, cors_allowed_origins
from backend.etf_metadata import ETF_METADATA
from backend.db import init_db
from backend.deps import get_current_user
from backend.market_cache import cache_key, chart_data_cache
from backend import pricing
from backend.optimizer import optimize_portfolio, compute_efficient_frontier
from backend.forecaster import (
    predict_returns,
    get_expected_returns,
    get_portfolio_data,
    compute_covariance_matrix,
    fetch_etf_data
)
from backend.news_service import fetch_news_for_ticker, NewsServiceError
from backend.news_pipeline import analyze_article, analyze_articles
from backend.news_aggregator import aggregate as aggregate_news
from backend.news_features import build_news_features
from backend.forecast_context import build_forecast_context
from backend.news_cache import analyzed_news_cache
from backend.routers import admin as admin_router
from backend.routers import assistant as assistant_router
from backend.routers import auth as auth_router
from backend.routers import portfolio as portfolio_router

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    lifespan=_lifespan,
    title="Dynamic Portfolio Optimizer",
    description="""
    API for ETF portfolio optimization with ML-based return forecasting.

    ## Features
    - **Forecast**: Predict 22-day ETF returns using per-ticker LSTM models (trained 2000 epochs)
    - **Optimize**: Find optimal portfolio allocation using various strategies
    - **Smart Invest**: Combined forecasting + optimization in one call
    - **Chart Data**: Historical prices, YTD returns, and forecast visualization

    ## Model Architecture
    - Individual LSTM model per ETF ticker for specialized predictions
    - 9 features: momentum (1m, 3m, 6m), volatility, RSI, position in 52-week range, correlation, max drawdown, region
    - Sequence length: 10 days

    ## Optimization Strategies
    - `max_sharpe`: Maximize risk-adjusted returns (Sharpe ratio)
    - `min_volatility`: Minimize portfolio risk
    - `risk_parity`: Equal risk contribution from each asset
    - `equal_weight`: Simple equal allocation

    ## Authentication
    Every endpoint below requires `Authorization: Bearer <token>` (obtained
    from `POST /auth/login`) except `/auth/register`, `/auth/login` and
    `/health`. `/admin/*` additionally requires an admin account.
    """,
    version=APP_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins(),
    allow_credentials=False,  # auth is a Bearer token (localStorage), not cookies
    allow_methods=["*"],
    allow_headers=["*"],
    # Without this, browsers cache a preflight OPTIONS response only very
    # briefly (Chromium defaults to 5s), so a chatty SPA calling the same
    # endpoint repeatedly (quotes, portfolio summary, ...) re-preflights on
    # almost every call. 10 minutes is well within how often CORS policy
    # here actually changes (never, at runtime) and cuts a real fraction of
    # the extra round trips React makes to FastAPI.
    max_age=600,
)

app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(portfolio_router.router)
app.include_router(assistant_router.router)

_AUTH = [Depends(get_current_user)]

# ETF metadata now lives in backend/etf_metadata.py (imported at the top of
# this file) — shared with backend/assistant_tools.py.


def get_historical_prices(tickers: List[str], period: str = "1y") -> Dict:
    """Fetch historical prices for charting. Cached for a short TTL — see
    `backend/market_cache.py`; identical to `calculate_ytd_returns` and
    `get_normalized_prices` below, this is requested with the same
    (tickers, period) very often (a `/smart-invest` re-run, a second user
    with the default universe)."""
    key = cache_key("historical_prices", tickers, period)
    cached = chart_data_cache.get(key)
    if cached is not None:
        return cached
    result = _get_historical_prices_uncached(tickers, period)
    chart_data_cache.set(key, result)
    return result


def _get_historical_prices_uncached(tickers: List[str], period: str = "1y") -> Dict:
    try:
        data = yf.download(tickers, period=period, progress=False)
        if data.empty:
            return {}

        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close']
        else:
            close = data[['Close']]
            close.columns = tickers

        # Convert to list format for JSON
        result = {
            "dates": [d.strftime('%Y-%m-%d') for d in close.index],
            "prices": {}
        }

        for ticker in tickers:
            if ticker in close.columns:
                prices = close[ticker].ffill().tolist()
                result["prices"][ticker] = [round(p, 2) if not pd.isna(p) else None for p in prices]

        return result
    except Exception as e:
        return {"error": str(e)}


def calculate_ytd_returns(tickers: List[str]) -> Dict[str, float]:
    """Calculate YTD returns for each ticker. Cached for a short TTL — see
    `get_historical_prices`."""
    start_of_year = datetime(datetime.now().year, 1, 1).strftime('%Y-%m-%d')
    key = cache_key("ytd_returns", tickers, start_of_year)
    cached = chart_data_cache.get(key)
    if cached is not None:
        return cached
    result = _calculate_ytd_returns_uncached(tickers, start_of_year)
    chart_data_cache.set(key, result)
    return result


def _calculate_ytd_returns_uncached(tickers: List[str], start_of_year: str) -> Dict[str, float]:
    try:
        data = yf.download(tickers, start=start_of_year, progress=False)

        if data.empty:
            return {}

        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close']
        else:
            close = data[['Close']]
            close.columns = tickers

        ytd_returns = {}
        for ticker in tickers:
            if ticker in close.columns:
                first_price = close[ticker].iloc[0]
                last_price = close[ticker].iloc[-1]
                if first_price > 0:
                    ytd_returns[ticker] = round(((last_price - first_price) / first_price) * 100, 2)

        return ytd_returns
    except:
        return {}


def get_normalized_prices(tickers: List[str], period: str = "6mo") -> Dict:
    """Get normalized prices (starting at 100) for comparison. Cached for a
    short TTL — see `get_historical_prices`."""
    key = cache_key("normalized_prices", tickers, period)
    cached = chart_data_cache.get(key)
    if cached is not None:
        return cached
    result = _get_normalized_prices_uncached(tickers, period)
    chart_data_cache.set(key, result)
    return result


def _get_normalized_prices_uncached(tickers: List[str], period: str = "6mo") -> Dict:
    try:
        data = yf.download(tickers, period=period, progress=False)
        if data.empty:
            return {}

        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close']
        else:
            close = data[['Close']]
            close.columns = tickers

        # Normalize to 100
        normalized = (close / close.iloc[0]) * 100

        result = {
            "dates": [d.strftime('%Y-%m-%d') for d in normalized.index],
            "prices": {}
        }

        for ticker in tickers:
            if ticker in normalized.columns:
                prices = normalized[ticker].ffill().tolist()
                result["prices"][ticker] = [round(p, 2) if not pd.isna(p) else None for p in prices]

        return result
    except Exception as e:
        return {"error": str(e)}


# ============== Basic Optimize Endpoint ==============

class OptimizeRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1)
    mu: List[float]
    cov: List[List[float]]
    risk_free: float = 0.0
    strategy: Literal["max_sharpe", "min_volatility", "risk_parity", "equal_weight"] = "max_sharpe"
    allow_short: bool = False


class OptimizeResponse(BaseModel):
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe: float


@app.post("/optimize", response_model=OptimizeResponse, dependencies=_AUTH)
def optimize(req: OptimizeRequest):
    """Basic portfolio optimization with provided returns and covariance."""
    n = len(req.tickers)

    if len(req.mu) != n:
        raise HTTPException(status_code=400, detail="mu length must match tickers length")

    cov = np.array(req.cov, dtype=float)
    if cov.shape != (n, n):
        raise HTTPException(status_code=400, detail="cov must be a square matrix (n x n)")

    mu = np.array(req.mu, dtype=float)

    w, metrics = optimize_portfolio(
        mu=mu,
        cov=cov,
        risk_free=req.risk_free,
        strategy=req.strategy,
        allow_short=req.allow_short
    )

    if len(w) != n:
        raise HTTPException(status_code=500, detail="optimizer returned wrong number of weights")

    weights = {t: float(wi) for t, wi in zip(req.tickers, w)}

    return OptimizeResponse(weights=weights, **metrics)


# ============== Forecasting Endpoints ==============

class ForecastRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1, description="List of ETF ticker symbols")
    model_path: Optional[str] = Field(
        default="trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs",
        description="Path to model directory containing per-ticker LSTM models"
    )
    start_date: str = Field("2010-01-01", description="Start date for historical data")


class TickerForecast(BaseModel):
    predicted_return_22d: Optional[float] = Field(None, description="Predicted 22-day return")
    last_actual_return_22d: float = Field(..., description="Last observed 22-day return")
    prediction_date: str = Field(..., description="Date of prediction")
    note: Optional[str] = None


class ForecastResponse(BaseModel):
    predictions: Dict[str, TickerForecast]
    tickers_processed: int
    model_loaded: bool


@app.post("/forecast", response_model=ForecastResponse, dependencies=_AUTH)
def forecast(req: ForecastRequest):
    """Generate 22-day return forecasts for given ETF tickers."""
    try:
        predictions = predict_returns(
            tickers=req.tickers,
            model_path=req.model_path,
            start_date=req.start_date
        )

        ticker_forecasts = {}
        model_loaded = True

        for ticker, pred_data in predictions.items():
            if pred_data.get('note'):
                model_loaded = False
            ticker_forecasts[ticker] = TickerForecast(
                predicted_return_22d=pred_data.get('predicted_return_22d'),
                last_actual_return_22d=pred_data['last_actual_return_22d'],
                prediction_date=pred_data['prediction_date'],
                note=pred_data.get('note')
            )

        return ForecastResponse(
            predictions=ticker_forecasts,
            tickers_processed=len(ticker_forecasts),
            model_loaded=model_loaded
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecasting error: {str(e)}")


# ============== Smart Invest - Combined Forecast + Optimize ==============

class SmartInvestRequest(BaseModel):
    tickers: List[str] = Field(
        default=["PSI", "IYW", "RING", "PICK", "NLR", "UTES", "LIT", "NANR", "GUNR", "XCEM", "PTLC", "FXU"],
        min_length=1,
        description="List of ETF ticker symbols to consider"
    )
    model_path: Optional[str] = Field(
        default="trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs",
        description="Path to trained model directory containing per-ticker LSTM models"
    )
    risk_free_rate: float = Field(
        default=0.05,
        description="Annual risk-free rate (e.g., 0.05 for 5%)"
    )
    strategy: Literal["max_sharpe", "min_volatility", "risk_parity", "equal_weight"] = Field(
        default="max_sharpe",
        description="Portfolio optimization strategy"
    )
    investment_amount: Optional[float] = Field(
        default=None,
        description="Total amount to invest (for calculating allocations)"
    )
    include_charts: bool = Field(
        default=True,
        description="Include chart data in response"
    )


class ETFAllocation(BaseModel):
    ticker: str
    name: str = Field(..., description="ETF name/sector")
    region: str = Field(..., description="Geographic region")
    weight_percent: float = Field(..., description="Allocation percentage (0-100)")
    amount: Optional[float] = Field(None, description="Amount to invest if investment_amount provided")
    predicted_return: float = Field(..., description="Predicted annualized return")
    predicted_return_capped: float = Field(..., description="Capped predicted return for display")
    historical_volatility: float = Field(..., description="Historical annualized volatility")
    ytd_return: float = Field(..., description="Year-to-date return")
    recommendation: str = Field(..., description="Investment recommendation")


class PortfolioMetrics(BaseModel):
    expected_annual_return: float = Field(..., description="Expected portfolio return (annualized)")
    expected_annual_return_percent: float = Field(..., description="Expected return as percentage")
    expected_annual_return_capped: float = Field(..., description="Capped return for display")
    annual_volatility: float = Field(..., description="Portfolio volatility (annualized)")
    annual_volatility_percent: float = Field(..., description="Volatility as percentage")
    sharpe_ratio: float = Field(..., description="Risk-adjusted return metric")
    diversification_score: float = Field(..., description="Portfolio diversification (0-1)")
    portfolio_ytd_return: float = Field(..., description="Weighted portfolio YTD return")


class GeographicAllocation(BaseModel):
    region: str
    allocation_percent: float


class ChartData(BaseModel):
    dates: List[str]
    prices: Dict[str, List[Optional[float]]]


class SmartInvestResponse(BaseModel):
    success: bool
    strategy_used: str
    allocations: List[ETFAllocation]
    portfolio_metrics: PortfolioMetrics
    geographic_allocation: List[GeographicAllocation]
    investment_amount: Optional[float]
    recommendation_summary: str
    top_picks: List[str] = Field(..., description="Top 3 ETFs to invest in")
    # Chart data
    price_evolution: Optional[ChartData] = None
    normalized_prices: Optional[ChartData] = None


@app.post("/smart-invest", response_model=SmartInvestResponse, dependencies=_AUTH)
def smart_invest(req: SmartInvestRequest):
    """
    Smart Investment Advisor - Forecast returns and optimize portfolio in one call.

    This endpoint:
    1. Fetches historical data for all specified ETFs
    2. Uses ML model to forecast expected returns
    3. Computes covariance matrix from historical data
    4. Optimizes portfolio allocation based on chosen strategy
    5. Returns detailed recommendations with allocation amounts
    6. Includes chart data for visualization
    """
    try:
        # Get portfolio data (forecasted returns + covariance)
        portfolio_data = get_portfolio_data(
            tickers=req.tickers,
            model_path=req.model_path
        )

        mu = portfolio_data["expected_returns"]
        cov = portfolio_data["covariance_matrix"]
        hist_vol = portfolio_data["historical_volatility"]

        # Get YTD returns
        ytd_returns = calculate_ytd_returns(req.tickers)

        # Optimize portfolio
        weights, metrics = optimize_portfolio(
            mu=mu,
            cov=cov,
            risk_free=req.risk_free_rate,
            strategy=req.strategy
        )

        # Build allocations list
        allocations = []
        geo_allocation = {}
        portfolio_ytd = 0.0

        for i, ticker in enumerate(req.tickers):
            weight = float(weights[i])
            weight_percent = round(weight * 100, 2)

            # Calculate amount if investment provided
            amount = None
            if req.investment_amount:
                amount = round(weight * req.investment_amount, 2)

            # Predicted return (annualized)
            pred_return = float(mu[i])
            pred_return_capped = min(pred_return, 1.0)  # Cap at 100%

            # Historical volatility
            ticker_vol = hist_vol.get(ticker, 0.0)

            # YTD return
            ytd_ret = ytd_returns.get(ticker, 0.0)
            portfolio_ytd += weight * ytd_ret

            # Get metadata
            metadata = ETF_METADATA.get(ticker, {"name": ticker, "region": "Other"})
            region = metadata["region"]

            # Geographic allocation
            geo_allocation[region] = geo_allocation.get(region, 0) + weight_percent

            # Generate recommendation
            if weight_percent >= 15:
                recommendation = "Strong Buy"
            elif weight_percent >= 10:
                recommendation = "Buy"
            elif weight_percent >= 5:
                recommendation = "Hold"
            elif weight_percent > 0:
                recommendation = "Light"
            else:
                recommendation = "Avoid"

            allocations.append(ETFAllocation(
                ticker=ticker,
                name=metadata["name"],
                region=region,
                weight_percent=weight_percent,
                amount=amount,
                predicted_return=round(pred_return, 4),
                predicted_return_capped=round(pred_return_capped * 100, 1),
                historical_volatility=round(ticker_vol, 4),
                ytd_return=round(ytd_ret, 2),
                recommendation=recommendation
            ))

        # Sort by weight (highest first)
        allocations.sort(key=lambda x: x.weight_percent, reverse=True)

        # Get top 3 picks
        top_picks = [a.ticker for a in allocations[:3] if a.weight_percent > 0]

        # Calculate diversification score (inverse of concentration)
        weights_array = np.array([a.weight_percent / 100 for a in allocations])
        herfindahl_index = np.sum(weights_array ** 2)
        diversification_score = round(1 - herfindahl_index, 2)

        # Cap expected return for display
        expected_return_capped = min(metrics["expected_return"], 1.0)

        # Portfolio metrics
        portfolio_metrics = PortfolioMetrics(
            expected_annual_return=round(metrics["expected_return"], 4),
            expected_annual_return_percent=round(metrics["expected_return"] * 100, 2),
            expected_annual_return_capped=round(expected_return_capped * 100, 1),
            annual_volatility=round(metrics["volatility"], 4),
            annual_volatility_percent=round(metrics["volatility"] * 100, 2),
            sharpe_ratio=round(metrics["sharpe"], 2),
            diversification_score=diversification_score,
            portfolio_ytd_return=round(portfolio_ytd, 2)
        )

        # Geographic allocation list
        geo_list = [
            GeographicAllocation(region=region, allocation_percent=round(pct, 1))
            for region, pct in sorted(geo_allocation.items(), key=lambda x: -x[1])
            if pct > 0
        ]

        # Generate summary
        summary = f"""Based on ML-forecasted returns and {req.strategy} optimization:
• Expected annual return: {portfolio_metrics.expected_annual_return_capped:.1f}%
• Portfolio volatility: {portfolio_metrics.annual_volatility_percent:.1f}%
• Sharpe ratio: {portfolio_metrics.sharpe_ratio:.2f}
• YTD performance: {portfolio_metrics.portfolio_ytd_return:+.1f}%
• Top recommendations: {', '.join(top_picks)}"""

        # Get chart data if requested
        price_evolution = None
        normalized_prices = None

        if req.include_charts:
            # Get 1 year of historical prices
            hist_data = get_historical_prices(req.tickers, period="1y")
            if "dates" in hist_data:
                price_evolution = ChartData(
                    dates=hist_data["dates"],
                    prices=hist_data["prices"]
                )

            # Get 6 months of normalized prices
            norm_data = get_normalized_prices(req.tickers, period="6mo")
            if "dates" in norm_data:
                normalized_prices = ChartData(
                    dates=norm_data["dates"],
                    prices=norm_data["prices"]
                )

        return SmartInvestResponse(
            success=True,
            strategy_used=req.strategy,
            allocations=allocations,
            portfolio_metrics=portfolio_metrics,
            geographic_allocation=geo_list,
            investment_amount=req.investment_amount,
            recommendation_summary=summary,
            top_picks=top_picks,
            price_evolution=price_evolution,
            normalized_prices=normalized_prices
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Smart invest error: {str(e)}")


# ============== Chart Data Endpoint ==============

class ChartDataRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1)
    period: str = Field(default="6mo", description="Time period: 1mo, 3mo, 6mo, 1y, 5y")
    normalize: bool = Field(default=True, description="Normalize prices to 100")


class ChartDataResponse(BaseModel):
    dates: List[str]
    prices: Dict[str, List[Optional[float]]]
    ytd_returns: Dict[str, float]


@app.post("/chart-data", response_model=ChartDataResponse, dependencies=_AUTH)
def get_chart_data(req: ChartDataRequest):
    """Get price data for charting."""
    try:
        if req.normalize:
            data = get_normalized_prices(req.tickers, req.period)
        else:
            data = get_historical_prices(req.tickers, req.period)

        if "error" in data:
            raise HTTPException(status_code=500, detail=data["error"])

        ytd = calculate_ytd_returns(req.tickers)

        return ChartDataResponse(
            dates=data.get("dates", []),
            prices=data.get("prices", {}),
            ytd_returns=ytd
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chart data error: {str(e)}")


# ============== Efficient Frontier ==============

class EfficientFrontierRequest(BaseModel):
    tickers: List[str] = Field(
        default=["PSI", "IYW", "RING", "PICK", "NLR", "UTES", "LIT", "NANR", "GUNR", "XCEM", "PTLC", "FXU"],
        min_length=2
    )
    model_path: Optional[str] = Field(default="trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs")
    risk_free_rate: float = Field(default=0.05)
    n_points: int = Field(default=50, ge=10, le=100)


class EfficientFrontierResponse(BaseModel):
    returns: List[float]
    volatilities: List[float]
    sharpes: List[float]
    max_sharpe_return: float
    max_sharpe_volatility: float
    min_vol_return: float
    min_vol_volatility: float


@app.post("/efficient-frontier", response_model=EfficientFrontierResponse, dependencies=_AUTH)
def efficient_frontier(req: EfficientFrontierRequest):
    """Compute the efficient frontier for visualization."""
    try:
        portfolio_data = get_portfolio_data(
            tickers=req.tickers,
            model_path=req.model_path
        )

        frontier = compute_efficient_frontier(
            mu=portfolio_data["expected_returns"],
            cov=portfolio_data["covariance_matrix"],
            risk_free=req.risk_free_rate,
            n_points=req.n_points
        )

        return EfficientFrontierResponse(
            returns=frontier["returns"],
            volatilities=frontier["volatilities"],
            sharpes=frontier["sharpes"],
            max_sharpe_return=frontier["max_sharpe_portfolio"]["expected_return"],
            max_sharpe_volatility=frontier["max_sharpe_portfolio"]["volatility"],
            min_vol_return=frontier["min_volatility_portfolio"]["expected_return"],
            min_vol_volatility=frontier["min_volatility_portfolio"]["volatility"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Efficient frontier error: {str(e)}")


# ============== News, Sentiment & Market Impact ==============
#
# Frontend (Streamlit) -> this API -> backend/news_service.py -> NewsAPI.
# NEWS_API_KEY lives only in backend/config.py; it is never placed in any
# response model below.

class SentimentModel(BaseModel):
    label: Literal["POSITIVE", "NEGATIVE", "NEUTRAL"]
    score: float = Field(..., ge=0, le=1)


class MarketImpactModel(BaseModel):
    direction: Literal["POSITIVE", "NEGATIVE", "NEUTRAL"]
    level: Literal["LOW", "MEDIUM", "HIGH"]
    confidence: float = Field(..., ge=0, le=1)


class NewsAnalyzeRequest(BaseModel):
    ticker: str
    headline: str = Field(..., min_length=1)
    description: Optional[str] = None
    content: Optional[str] = None


class NewsAnalyzeResponse(BaseModel):
    ticker: str
    sentiment: SentimentModel
    marketImpact: MarketImpactModel


@app.post("/news/analyze", response_model=NewsAnalyzeResponse, dependencies=_AUTH)
def analyze_news(req: NewsAnalyzeRequest):
    """Sentiment + market impact for a single, user-supplied headline/article."""
    article = {
        "title": req.headline,
        "description": req.description or "",
        "content": req.content or "",
        "source": "manual",
        "url": None,
        "publishedAt": None,
    }
    analyzed = analyze_article(article)
    if analyzed is None:
        raise HTTPException(status_code=400, detail="Headline/content is too short to analyze.")

    return NewsAnalyzeResponse(
        ticker=req.ticker.upper(),
        sentiment=SentimentModel(**analyzed["sentiment"]),
        marketImpact=MarketImpactModel(**analyzed["market_impact"]),
    )


_NEWS_ERROR_STATUS = {
    "no_api_key": (503, "News service is not configured on the server."),
    "invalid_key": (503, "News service authentication failed."),
    "rate_limit": (429, "News service rate limit reached — try again shortly."),
    "timeout": (504, "News service timed out."),
    "unavailable": (503, "News service is temporarily unavailable."),
}


def _news_error_to_http(exc: NewsServiceError) -> HTTPException:
    status_code, message = _NEWS_ERROR_STATUS.get(exc.kind, (503, "News service error."))
    return HTTPException(status_code=status_code, detail=message)


def _get_analyzed_news(ticker: str) -> list:
    """Fetch + preprocess + score recent news for a ticker, cached ~20 min."""
    ticker = ticker.upper()

    def _load():
        company_name = ETF_METADATA.get(ticker, {}).get("name")
        query_name = f"{company_name} ETF" if company_name else None
        try:
            raw_articles = fetch_news_for_ticker(ticker, company_name=query_name)
        except NewsServiceError as exc:
            raise _news_error_to_http(exc)
        analyzed = analyze_articles(raw_articles)
        analyzed.sort(key=lambda a: a.get("publishedAt") or "", reverse=True)
        return analyzed

    cached = analyzed_news_cache.get(ticker)
    if cached is not None:
        return cached
    result = _load()
    analyzed_news_cache.set(ticker, result)
    return result


class NewsItemModel(BaseModel):
    title: str
    description: str
    source: str
    url: Optional[str]
    publishedAt: Optional[str]
    sentiment: SentimentModel
    marketImpact: MarketImpactModel
    recencyWeight: float


class NewsListResponse(BaseModel):
    ticker: str
    items: List[NewsItemModel]
    count: int


@app.get("/news/{ticker}", response_model=NewsListResponse, dependencies=_AUTH)
def get_ticker_news(ticker: str):
    """Recent news for `ticker`, each scored with sentiment + market impact."""
    analyzed = _get_analyzed_news(ticker)
    items = [
        NewsItemModel(
            title=a["title"], description=a["description"], source=a["source"],
            url=a["url"], publishedAt=a["publishedAt"],
            sentiment=SentimentModel(**a["sentiment"]),
            marketImpact=MarketImpactModel(**a["market_impact"]),
            recencyWeight=a["recency_weight"],
        )
        for a in analyzed
    ]
    return NewsListResponse(ticker=ticker.upper(), items=items, count=len(items))


class NewsSummaryResponse(BaseModel):
    ticker: str
    news_count: int
    positive_news_count: int
    negative_news_count: int
    neutral_news_count: int
    weighted_sentiment: float
    overall_sentiment: str
    overall_market_impact: str
    overall_confidence: float
    average_confidence: float


@app.get("/news/{ticker}/summary", response_model=NewsSummaryResponse, dependencies=_AUTH)
def get_ticker_news_summary(ticker: str):
    """Aggregated sentiment/impact across today's news for `ticker`."""
    analyzed = _get_analyzed_news(ticker)
    summary = aggregate_news(analyzed)
    return NewsSummaryResponse(ticker=ticker.upper(), **summary)


class MarketImpactRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1)


class TickerImpactModel(BaseModel):
    ticker: str
    news_count: int
    weighted_sentiment: float
    overall_sentiment: str
    overall_market_impact: str
    overall_confidence: float


class MarketImpactResponse(BaseModel):
    tickers: List[TickerImpactModel]
    overall: NewsSummaryResponse
    failed_tickers: List[str]


@app.post("/news/market-impact", response_model=MarketImpactResponse, dependencies=_AUTH)
def get_market_impact(req: MarketImpactRequest):
    """News-driven sentiment/impact across a whole universe of tickers.

    Per-ticker failures (rate limit, no news…) are skipped rather than
    failing the whole request — `failed_tickers` reports which ones, so the
    view can still render a partial market read. `overall` pools every
    analyzed article across all tickers through the same weighting as a
    single-ticker summary, giving one market-wide reading rather than an
    average of averages.
    """
    tickers = [t.upper() for t in dict.fromkeys(req.tickers)]
    per_ticker: list[TickerImpactModel] = []
    all_articles: list = []
    failed: list[str] = []

    for ticker in tickers:
        try:
            analyzed = _get_analyzed_news(ticker)
        except HTTPException:
            failed.append(ticker)
            continue
        summary = aggregate_news(analyzed)
        per_ticker.append(TickerImpactModel(ticker=ticker, **{
            k: summary[k] for k in (
                "news_count", "weighted_sentiment", "overall_sentiment",
                "overall_market_impact", "overall_confidence",
            )
        }))
        all_articles.extend(analyzed)

    overall = aggregate_news(all_articles)
    return MarketImpactResponse(
        tickers=per_ticker,
        overall=NewsSummaryResponse(ticker="MARKET", **overall),
        failed_tickers=failed,
    )


class ForecastContextRequest(BaseModel):
    ticker: str
    model_path: Optional[str] = Field(
        default="trained_models_LSTM_2000_epochs/trained_models_LSTM_2000_epochs",
    )
    current_price: Optional[float] = Field(
        default=None, description="Pass the UI's already-known quote to avoid a second fetch."
    )


class BaseForecastModel(BaseModel):
    predicted_return_22d: Optional[float]
    used_return_22d: float
    forecast_price: Optional[float]
    model_loaded: bool
    note: Optional[str]
    prediction_date: Optional[str]


class NewsContextForecastModel(BaseModel):
    predicted_return_22d: float
    forecast_price: Optional[float]
    adjustment_22d: float
    combined_news_signal: float
    max_adjustment_22d: float


class ForecastContextResponse(BaseModel):
    ticker: str
    current_price: Optional[float]
    base_forecast: BaseForecastModel
    news_context_forecast: NewsContextForecastModel
    potential_direction: str
    news_features: Dict[str, float | int]
    disclaimer: str


@app.post("/forecast/context", response_model=ForecastContextResponse, dependencies=_AUTH)
def forecast_context(req: ForecastContextRequest):
    """Base LSTM forecast (unchanged) vs. news-context forecast, side by side.

    A news-service failure degrades to "no news features" (all zeros) rather
    than blocking the base forecast — the comparison still renders, just
    without a news tilt.
    """
    ticker = req.ticker.upper()
    try:
        analyzed = _get_analyzed_news(ticker)
    except HTTPException:
        analyzed = []

    features = build_news_features(analyzed)

    try:
        context = build_forecast_context(
            ticker, features, model_path=req.model_path, current_price=req.current_price,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast context error: {str(e)}")

    return ForecastContextResponse(**context)


# ============== Market Quotes ==============
#
# The one REST endpoint every frontend needs for "current price + day
# change" — Streamlit's `services/market.py` fetches this Python-side
# in-process, which a separate frontend (React) can't do; this is that same
# data (via `backend/pricing.py`, cached ~20s) over HTTP instead.

class QuoteModel(BaseModel):
    ticker: str
    price: float
    previous_close: float
    change_abs: float
    change_pct: float


class QuotesResponse(BaseModel):
    quotes: Dict[str, QuoteModel]
    missing: List[str] = Field(default_factory=list)


@app.get("/market/quotes", response_model=QuotesResponse, dependencies=_AUTH)
def market_quotes(tickers: str):
    """`tickers` is a comma-separated list, e.g. `?tickers=SPY,QQQ,PSI`."""
    requested = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not requested:
        raise HTTPException(status_code=400, detail="At least one ticker is required.")

    raw = pricing.get_quotes(requested)
    quotes = {t: QuoteModel(ticker=t, **raw[t]) for t in requested if t in raw}
    missing = [t for t in requested if t not in raw]
    return QuotesResponse(quotes=quotes, missing=missing)


class OHLCBar(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class OHLCResponse(BaseModel):
    ticker: str
    period: str
    bars: List[OHLCBar]


_OHLC_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y"}


@app.get("/market/ohlc", response_model=OHLCResponse, dependencies=_AUTH)
def market_ohlc(ticker: str, period: str = "6mo"):
    """Real OHLCV bars for one ticker — feeds the Markets page candlestick
    chart. Never fabricates candles: an unknown ticker or a Yahoo Finance
    failure returns an empty `bars` list, not synthetic data."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="A ticker is required.")
    if period not in _OHLC_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"period must be one of {sorted(_OHLC_PERIODS)}.",
        )
    bars = pricing.get_ohlc(ticker, period)
    return OHLCResponse(ticker=ticker, period=period, bars=bars)


# ============== Health Check ==============

@app.get("/health")
def health_check():
    """API health check endpoint. Deliberately public — used by the
    pre-login connectivity probe."""
    return {"status": "healthy", "version": APP_VERSION}
