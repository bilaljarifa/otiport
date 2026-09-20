# -*- coding: utf-8 -*-
"""API-layer tests for `/analytics/*` — auth gating and request/response
wiring. The underlying computation is already covered by
`test_model_evaluation.py` / `test_backtester.py`; here the module-level
functions are mocked so these tests stay fast and only check the HTTP
contract (status codes, auth, error mapping, response shape)."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from backend.backtester import BacktestError


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_model_evaluation_endpoints_require_auth(client):
    assert client.get("/analytics/model-evaluation/universe").status_code == 401
    assert client.get("/analytics/model-evaluation/summary").status_code == 401
    assert client.get("/analytics/model-evaluation/PSI").status_code == 401


def test_backtest_endpoint_requires_auth(client):
    response = client.post("/analytics/backtest", json={
        "tickers": ["PSI"], "start_date": "2020-01-01", "end_date": "2020-06-01",
    })
    assert response.status_code == 401


def test_model_evaluation_universe_lists_the_12_trained_tickers(client, register_user):
    user = register_user(username="evaluser")
    response = client.get("/analytics/model-evaluation/universe", headers=_headers(user["access_token"]))
    assert response.status_code == 200
    tickers = response.json()["tickers"]
    assert len(tickers) == 12
    assert "PSI" in tickers


def test_model_evaluation_summary_returns_no_series_payload(client, register_user):
    user = register_user(username="evaluser2")
    fake_result = {
        "ticker": "PSI", "status": "ok",
        "train_period": {"start": "2012-01-01", "end": "2019-01-01", "rows": 1000},
        "validation_period": {"start": "2019-01-02", "end": "2020-01-01", "rows": 200},
        "test_period": {"start": "2020-01-02", "end": "2021-01-01", "rows": 200},
        "validation_metrics": {
            "mae": 0.01, "rmse": 0.02, "mape": None, "mape_observations": 0,
            "directional_accuracy": 55.0, "observations": 200,
        },
        "test_metrics": {
            "mae": 0.01, "rmse": 0.02, "mape": 12.5, "mape_observations": 180,
            "directional_accuracy": 60.0, "observations": 200,
        },
        "validation_series": {"dates": ["2019-01-02"], "actual": [0.01], "predicted": [0.02]},
        "test_series": {"dates": ["2020-01-02"], "actual": [0.01], "predicted": [0.02]},
    }
    with patch(
        "backend.routers.analytics.evaluate_universe",
        return_value={t: fake_result for t in [
            "PSI", "IYW", "RING", "PICK", "NLR", "UTES", "LIT", "NANR", "GUNR", "XCEM", "PTLC", "FXU",
        ]},
    ):
        response = client.get(
            "/analytics/model-evaluation/summary", headers=_headers(user["access_token"]),
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["tickers"]) == 12
    assert body["tickers"][0]["validation_series"] is None
    assert body["tickers"][0]["test_series"] is None
    assert body["tickers"][0]["test_metrics"]["mape"] == 12.5
    assert len(body["methodology_notes"]) > 0


def test_model_evaluation_detail_includes_series(client, register_user):
    user = register_user(username="evaluser3")
    fake_result = {
        "ticker": "PSI", "status": "ok",
        "train_period": {"start": "2012-01-01", "end": "2019-01-01", "rows": 1000},
        "validation_period": {"start": "2019-01-02", "end": "2020-01-01", "rows": 200},
        "test_period": {"start": "2020-01-02", "end": "2021-01-01", "rows": 200},
        "validation_metrics": None,
        "test_metrics": {
            "mae": 0.01, "rmse": 0.02, "mape": None, "mape_observations": 0,
            "directional_accuracy": 60.0, "observations": 200,
        },
        "validation_series": {"dates": [], "actual": [], "predicted": []},
        "test_series": {"dates": ["2020-01-02"], "actual": [0.01], "predicted": [0.015]},
    }
    with patch("backend.routers.analytics.evaluate_ticker", return_value=fake_result):
        response = client.get(
            "/analytics/model-evaluation/PSI", headers=_headers(user["access_token"]),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["evaluation"]["test_series"]["dates"] == ["2020-01-02"]


def test_backtest_endpoint_maps_backtest_error_to_400(client, register_user):
    user = register_user(username="btuser")
    with patch("backend.routers.analytics.run_backtest", side_effect=BacktestError("bad window")):
        response = client.post(
            "/analytics/backtest",
            headers=_headers(user["access_token"]),
            json={"tickers": ["PSI"], "start_date": "2020-06-01", "end_date": "2020-01-01"},
        )
    assert response.status_code == 400
    assert "bad window" in response.text


def test_backtest_endpoint_returns_wired_response(client, register_user):
    user = register_user(username="btuser2")
    fake_result = {
        "inputs": {
            "tickers": ["PSI"], "start_date": "2020-01-01", "end_date": "2020-06-01",
            "initial_capital": 10000.0, "strategy": "max_sharpe", "risk_free_rate": 0.0,
            "benchmark_ticker": "SPY",
        },
        "equity_curve": [{"date": "2020-01-01", "strategy_equity": 10000.0, "benchmark_equity": 10000.0}],
        "rebalance_dates": ["2020-01-01"],
        "trades": [{"date": "2020-01-01", "ticker": "PSI", "side": "BUY", "quantity": 10.0, "price": 100.0, "notional": 1000.0}],
        "num_trades": 1,
        "winning_periods": 0,
        "losing_periods": 0,
        "flat_periods": 1,
        "win_rate_pct": None,
        "strategy_metrics": {
            "total_return_pct": 0.0, "annualized_return_pct": 0.0, "annualized_volatility_pct": 0.0,
            "sharpe_ratio": 0.0, "max_drawdown_pct": 0.0, "trading_days": 1,
        },
        "benchmark_metrics": None,
        "methodology_notes": ["note one"],
    }
    with patch("backend.routers.analytics.run_backtest", return_value=fake_result):
        response = client.post(
            "/analytics/backtest",
            headers=_headers(user["access_token"]),
            json={"tickers": ["PSI"], "start_date": "2020-01-01", "end_date": "2020-06-01"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["num_trades"] == 1
    assert body["methodology_notes"] == ["note one"]


def _fake_backtest_result():
    return {
        "inputs": {
            "tickers": ["PSI"], "start_date": "2020-01-01", "end_date": "2020-06-01",
            "initial_capital": 10000.0, "strategy": "max_sharpe", "risk_free_rate": 0.0,
            "benchmark_ticker": "SPY",
        },
        "equity_curve": [{"date": "2020-01-01", "strategy_equity": 10000.0, "benchmark_equity": 10000.0}],
        "rebalance_dates": ["2020-01-01"],
        "trades": [],
        "num_trades": 0,
        "winning_periods": 0,
        "losing_periods": 0,
        "flat_periods": 1,
        "win_rate_pct": None,
        "strategy_metrics": {
            "total_return_pct": 0.0, "annualized_return_pct": 0.0, "annualized_volatility_pct": 0.0,
            "sharpe_ratio": 0.0, "max_drawdown_pct": 0.0, "trading_days": 1,
        },
        "benchmark_metrics": None,
        "methodology_notes": ["note one"],
    }


def _poll_until_finished(client, headers, job_id, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/analytics/backtest/status/{job_id}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.02)
    raise AssertionError("Backtest job did not finish in time")


def test_backtest_job_endpoints_require_auth(client):
    assert client.post("/analytics/backtest/start", json={
        "tickers": ["PSI"], "start_date": "2020-01-01", "end_date": "2020-06-01",
    }).status_code == 401
    assert client.get("/analytics/backtest/status/some-id").status_code == 401


def test_unknown_backtest_job_id_returns_404(client, register_user):
    user = register_user(username="btjobuser0")
    response = client.get(
        "/analytics/backtest/status/does-not-exist", headers=_headers(user["access_token"]),
    )
    assert response.status_code == 404


def test_backtest_job_runs_in_background_and_reports_real_progress(client, register_user):
    """The job must go from `running` (with real, monotonically increasing
    progress fed by `run_backtest`'s own callback) to `done` with the exact
    same result shape the synchronous endpoint returns — never a fabricated
    progress value."""
    user = register_user(username="btjobuser1")
    headers = _headers(user["access_token"])

    progress_events = []

    def fake_run_backtest(*, on_progress=None, **kwargs):
        if on_progress:
            on_progress("fetching_data", 0, 1, None, None)
            on_progress("simulating", 1, 2, "2020-01-01", "2020-02-01")
            on_progress("simulating", 2, 2, "2020-02-01", "2020-03-01")
            on_progress("done", 2, 2, None, None)
        return _fake_backtest_result()

    with patch("backend.backtest_jobs.run_backtest", side_effect=fake_run_backtest):
        start_response = client.post(
            "/analytics/backtest/start",
            headers=headers,
            json={"tickers": ["PSI"], "start_date": "2020-01-01", "end_date": "2020-06-01"},
        )
        assert start_response.status_code == 200
        job_id = start_response.json()["job_id"]

        final = _poll_until_finished(client, headers, job_id)

    assert final["status"] == "done"
    assert final["result"]["num_trades"] == 0
    assert final["progress"]["phase"] == "done"
    assert final["progress"]["completed"] == final["progress"]["total"]


def test_backtest_job_surfaces_backtest_error(client, register_user):
    user = register_user(username="btjobuser2")
    headers = _headers(user["access_token"])

    with patch("backend.backtest_jobs.run_backtest", side_effect=BacktestError("window too short")):
        start_response = client.post(
            "/analytics/backtest/start",
            headers=headers,
            json={"tickers": ["PSI"], "start_date": "2020-01-01", "end_date": "2020-06-01"},
        )
        job_id = start_response.json()["job_id"]
        final = _poll_until_finished(client, headers, job_id)

    assert final["status"] == "error"
    assert "window too short" in final["error"]
    assert final["result"] is None


def test_model_comparison_requires_auth(client):
    assert client.get("/analytics/model-comparison/PSI").status_code == 401


def test_model_comparison_endpoint_wires_real_result(client, register_user):
    user = register_user(username="mcuser1")
    fake_result = {
        "ticker": "PSI", "status": "ok",
        "models": [
            {"model": "naive", "label": "Naive / Last Value", "status": "ok",
             "mae": 0.05, "rmse": 0.07, "mape": None, "mape_observations": 0,
             "directional_accuracy": 50.0, "observations": 100},
            {"model": "lstm", "label": "LSTM (existing model)", "status": "ok",
             "mae": 0.03, "rmse": 0.04, "mape": None, "mape_observations": 0,
             "directional_accuracy": 60.0, "observations": 100},
        ],
        "test_period": {"start": "2024-01-01", "end": "2024-06-01", "observations": 100},
        "methodology": {
            "target": "22-trading-day forward return (return_22d)",
            "forecast_horizon_days": 22, "sequence_length": 10,
            "train_fraction_pct": 70.0, "validation_fraction_pct": 15.0, "test_fraction_pct": 15.0,
        },
    }
    with patch("backend.routers.analytics.compare_models", return_value=fake_result):
        response = client.get(
            "/analytics/model-comparison/PSI", headers=_headers(user["access_token"]),
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["models"]) == 2
    assert body["models"][1]["model"] == "lstm"
    assert body["test_period"]["observations"] == 100


def test_model_comparison_maps_value_error_to_502(client, register_user):
    user = register_user(username="mcuser2")
    with patch("backend.routers.analytics.compare_models", side_effect=ValueError("no data")):
        response = client.get(
            "/analytics/model-comparison/PSI", headers=_headers(user["access_token"]),
        )
    assert response.status_code == 502
