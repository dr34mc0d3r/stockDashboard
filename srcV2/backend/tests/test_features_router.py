"""Router tests for the Stage 3 feature endpoints (catalog + compute)."""

from datetime import datetime, timedelta

from models import OhlcvBar

TEN_KEYS = {"sma", "ema", "bollinger", "vwap", "rsi", "macd", "stochastic", "atr", "adx", "obv"}


def seed_bars(session, symbol="AAPL", timeframe="1m", n=30):
    """Gently rising bars so indicators have a real range to chew on."""
    t0 = datetime(2025, 1, 2, 14, 30)
    for i in range(n):
        base = 100 + i * 0.5
        session.add(
            OhlcvBar(
                symbol=symbol,
                timeframe=timeframe,
                ts=t0 + timedelta(minutes=i),
                open=base,
                high=base + 1.5,
                low=base - 1.2,
                close=base + 0.3,
                volume=1_000 + i * 10,
            )
        )
    session.commit()


def test_catalog_lists_the_ten_with_params_and_placement(client):
    body = client.get("/api/v1/indicators/catalog").json()

    entries = {e["key"]: e for e in body["indicators"]}
    assert set(entries) == TEN_KEYS
    assert entries["sma"]["placement"] == "overlay"
    assert entries["rsi"]["placement"] == "pane"
    macd_params = {p["name"]: p for p in entries["macd"]["params"]}
    assert macd_params["fast"]["default"] == 12


def test_compute_returns_bars_and_aligned_series(client, session):
    seed_bars(session, n=30)

    res = client.post(
        "/api/v1/indicators",
        json={
            "symbol": "aapl",
            "timeframe": "1m",
            "indicators": [
                {"name": "sma", "params": {"period": 5}},
                {"name": "rsi", "params": {}},
            ],
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["symbol"] == "AAPL"  # normalized at the edge
    assert body["bar_count"] == 30
    assert len(body["bars"]) == 30
    assert set(body["indicators"]) == {"sma", "rsi"}
    sma = body["indicators"]["sma"]
    assert sma["params"] == {"period": 5}
    # Series aligned 1:1 with the bars; warm-up values are null.
    assert len(sma["series"]["sma"]) == 30
    assert sma["series"]["sma"][0]["value"] is None
    assert sma["series"]["sma"][-1]["value"] is not None


def test_compute_unknown_indicator_is_400(client, session):
    seed_bars(session, n=5)

    res = client.post(
        "/api/v1/indicators",
        json={"symbol": "AAPL", "timeframe": "1m", "indicators": [{"name": "nope"}]},
    )

    assert res.status_code == 400
    assert "Unknown indicator" in res.json()["detail"]


def test_compute_with_no_stored_bars_returns_empty(client):
    res = client.post(
        "/api/v1/indicators",
        json={"symbol": "AAPL", "timeframe": "1m", "indicators": [{"name": "sma"}]},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["bar_count"] == 0
    assert body["bars"] == []
    # Indicator still computed (over zero bars -> empty series).
    assert body["indicators"]["sma"]["series"]["sma"] == []
