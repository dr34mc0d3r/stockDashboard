"""Router tests for the Stage 1 data endpoints (inventory / bars / delete).

Bars are seeded straight into the test DB — the /ingest endpoint itself is not
exercised here because its UPSERT uses a MySQL-only statement that SQLite can't
run (and the Alpaca call is external anyway).
"""

from datetime import datetime, timedelta

from models import OhlcvBar


def seed_bars(session, symbol="AAPL", timeframe="1m", n=5, start=None):
    """Insert n one-minute bars with steadily rising close prices."""
    t0 = start or datetime(2025, 1, 2, 14, 30)
    for i in range(n):
        session.add(
            OhlcvBar(
                symbol=symbol,
                timeframe=timeframe,
                ts=t0 + timedelta(minutes=i),
                open=100 + i,
                high=101 + i,
                low=99 + i,
                close=100.5 + i,
                volume=1_000 + i,
            )
        )
    session.commit()


def test_inventory_empty(client):
    assert client.get("/api/v1/inventory").json() == []


def test_inventory_groups_per_symbol_timeframe(client, session):
    seed_bars(session, "AAPL", "1m", n=3)
    seed_bars(session, "TSLA", "1h", n=2)

    items = client.get("/api/v1/inventory").json()

    assert [(i["symbol"], i["timeframe"], i["bar_count"]) for i in items] == [
        ("AAPL", "1m", 3),
        ("TSLA", "1h", 2),
    ]
    assert items[0]["earliest"] < items[0]["latest"]


def test_bars_returns_oldest_first_and_respects_limit(client, session):
    seed_bars(session, n=5)

    res = client.get("/api/v1/bars", params={"symbol": "AAPL", "limit": 3}).json()

    assert len(res) == 3
    assert [b["ts"] for b in res] == sorted(b["ts"] for b in res)
    assert res[0]["open"] == 100.0


def test_bars_filters_by_date_range(client, session):
    seed_bars(session, n=5)  # 14:30 .. 14:34

    # Boundaries fall between bars: SQLite compares these as strings, and its
    # stored timestamps carry microseconds, so exact-equal boundaries are a
    # storage-format quirk rather than something worth pinning down here.
    res = client.get(
        "/api/v1/bars",
        params={
            "symbol": "AAPL",
            "start": "2025-01-02 14:30:30",
            "end": "2025-01-02 14:33:30",
        },
    ).json()

    assert len(res) == 3  # 14:31, 14:32, 14:33


def test_bars_symbol_is_case_insensitive(client, session):
    seed_bars(session, "AAPL", n=2)

    res = client.get("/api/v1/bars", params={"symbol": "aapl"}).json()

    assert len(res) == 2


def test_delete_bars_removes_rows_and_reports_count(client, session):
    seed_bars(session, "AAPL", "1m", n=4)
    seed_bars(session, "AAPL", "1h", n=2)  # different timeframe must survive

    res = client.delete("/api/v1/bars", params={"symbol": "aapl", "timeframe": "1m"})

    assert res.json()["deleted"] == 4
    remaining = client.get("/api/v1/inventory").json()
    assert [(i["symbol"], i["timeframe"]) for i in remaining] == [("AAPL", "1h")]
