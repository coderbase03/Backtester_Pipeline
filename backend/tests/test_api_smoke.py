from fastapi.testclient import TestClient
import pytest

from app.main import app


client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


def test_strategies_listed():
    response = client.get("/api/strategies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_data_endpoints_work():
    symbols = client.get("/api/data/symbols")
    summary = client.get("/api/data/summary")
    assert symbols.status_code == 200
    assert summary.status_code == 200
    assert isinstance(symbols.json(), list)
    assert isinstance(summary.json(), list)


def test_backtest_history_endpoint():
    response = client.get("/api/backtest/history?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_backtest_run_with_cached_symbol_or_skip():
    symbols_resp = client.get("/api/data/symbols")
    assert symbols_resp.status_code == 200
    symbols = symbols_resp.json()
    if not symbols:
        pytest.skip("No cached symbol in local DB for deterministic backtest smoke test.")

    first = symbols[0]
    interval = first.get("intervals", ["1h"])[0] if first.get("intervals") else "1h"
    payload = {
        "strategy": "sma",
        "symbol": first["symbol"],
        "source": "tradingview",
        "exchange": first.get("exchange"),
        "interval": interval,
        "n_bars": 200,
        "initial_cash": 100000,
        "commission": 0.001,
    }

    response = client.post("/api/backtest/run", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "run_id" in body
    assert "total_return" in body


def test_converter_returns_502_on_failure(monkeypatch):
    from app.services import converter_service

    def _fail(*args, **kwargs):
        raise RuntimeError("forced conversion failure")

    monkeypatch.setattr(converter_service, "convert_pine", _fail)

    response = client.post(
        "/api/converter/pine-to-python",
        json={"code": "indicator('x')", "direction": "pine_to_python", "model": "glm-4.7"},
    )
    assert response.status_code == 502
