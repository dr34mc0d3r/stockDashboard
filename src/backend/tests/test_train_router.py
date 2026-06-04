"""Router tests for the Stage 2 training endpoints.

`start_training` is monkeypatched to a no-op so no real torch thread spawns —
these tests cover the HTTP contract and the TrainingRun bookkeeping, not the
training loop itself (that's verified end-to-end through the UI).
"""

from datetime import datetime, timedelta

import routers.train
from models import OhlcvBar, TrainingRun


def seed_bars(session, symbol="AAPL", timeframe="1m", n=5):
    t0 = datetime(2025, 1, 2, 14, 30)
    for i in range(n):
        session.add(
            OhlcvBar(
                symbol=symbol,
                timeframe=timeframe,
                ts=t0 + timedelta(minutes=i),
                open=100,
                high=101,
                low=99,
                close=100.5,
                volume=1_000,
            )
        )
    session.commit()


def seed_run(session, **overrides):
    fields = {
        "stage": "lstm",
        "symbol": "AAPL",
        "timeframe": "1m",
        "status": "done",
        "hyperparams": {"seq_len": 60},
        "progress": [],
        **overrides,
    }
    run = TrainingRun(**fields)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def test_train_without_stored_bars_is_400(client, monkeypatch):
    monkeypatch.setattr(routers.train, "start_training", lambda *a, **k: None)

    res = client.post(
        "/api/v1/train/lstm",
        json={"symbol": "AAPL", "timeframe": "1m", "hyperparams": {}},
    )

    assert res.status_code == 400
    assert "No stored bars" in res.json()["detail"]


def test_train_creates_a_queued_run(client, session, monkeypatch):
    calls = []
    monkeypatch.setattr(routers.train, "start_training", lambda *a, **k: calls.append(a))
    seed_bars(session)

    res = client.post(
        "/api/v1/train/lstm",
        json={"symbol": "aapl", "timeframe": "1m", "hyperparams": {"seq_len": 30}},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "queued"
    assert body["symbol"] == "AAPL"  # schema validator uppercases
    assert body["hyperparams"]["seq_len"] == 30
    assert len(calls) == 1  # worker was kicked off exactly once


def test_runs_list_is_newest_first_and_filterable(client, session):
    seed_run(session, stage="lstm")
    seed_run(session, stage="lstm")
    seed_run(session, stage="other")

    runs = client.get("/api/v1/runs", params={"stage": "lstm"}).json()

    assert [r["stage"] for r in runs] == ["lstm", "lstm"]
    assert runs[0]["id"] > runs[1]["id"]

    limited = client.get("/api/v1/runs", params={"limit": 1}).json()
    assert len(limited) == 1


def test_get_run_found_and_missing(client, session):
    run = seed_run(session)

    assert client.get(f"/api/v1/runs/{run.id}").json()["id"] == run.id
    assert client.get("/api/v1/runs/99999").status_code == 404


def test_predictions_require_a_finished_run_with_artifact(client, session):
    unfinished = seed_run(session, status="running")
    no_artifact = seed_run(session, status="done", artifact_path=None)

    assert client.get(f"/api/v1/runs/{unfinished.id}/predictions").status_code == 400
    assert client.get(f"/api/v1/runs/{no_artifact.id}/predictions").status_code == 400
    assert client.get("/api/v1/runs/99999/predictions").status_code == 404
