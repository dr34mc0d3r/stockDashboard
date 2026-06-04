"""Router + prep-job tests for Stage 4.

The FinBERT scorer is monkeypatched to a deterministic fake and the news
client to canned articles — tests never download the model or hit the network.
The prep body (run_prep) is exercised synchronously against the test session.
"""

from datetime import datetime

import routers.sentiment
from models import NewsArticle, TrainingRun
from services.sentiment import prep_service


def fake_score_headlines(headlines):
    """Positive iff the headline contains 'beats'; negative iff 'misses'."""
    out = []
    for h in headlines:
        if "beats" in h:
            out.append({"pos": 0.9, "neg": 0.05, "neutral": 0.05})
        elif "misses" in h:
            out.append({"pos": 0.05, "neg": 0.9, "neutral": 0.05})
        else:
            out.append({"pos": 0.1, "neg": 0.1, "neutral": 0.8})
    return out


def fake_articles():
    return [
        {
            "id": "1",
            "ts": datetime(2025, 6, 2, 9),
            "headline": "TSLA beats estimates",
            "source": "bz",
            "url": "u1",
        },
        {
            "id": "2",
            "ts": datetime(2025, 6, 2, 15),
            "headline": "TSLA misses on margins",
            "source": "bz",
            "url": "u2",
        },
        {
            "id": "3",
            "ts": datetime(2025, 6, 4, 10),
            "headline": "TSLA opens new factory",
            "source": "bz",
            "url": "u3",
        },
    ]


def seed_run(session, **overrides):
    fields = {
        "stage": "finbert-prep",
        "symbol": "TSLA",
        "timeframe": "1d",
        "start": "2025-06-01",
        "end": "2025-06-30",
        "status": "running",
        "hyperparams": {"max_articles": 300},
        "progress": [],
        **overrides,
    }
    run = TrainingRun(**fields)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def test_prepare_creates_a_queued_prep_run(client, monkeypatch):
    calls = []
    monkeypatch.setattr(routers.sentiment, "start_prep", lambda rid: calls.append(rid))

    res = client.post(
        "/api/v1/sentiment/prepare",
        json={"symbol": "tsla", "start": "2025-06-01", "end": "2025-06-30", "max_articles": 50},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["stage"] == "finbert-prep"
    assert body["status"] == "queued"
    assert body["symbol"] == "TSLA"
    assert body["hyperparams"] == {"max_articles": 50}
    assert calls == [body["id"]]


def test_prepare_rejects_inverted_range(client, monkeypatch):
    monkeypatch.setattr(routers.sentiment, "start_prep", lambda rid: None)
    res = client.post(
        "/api/v1/sentiment/prepare",
        json={"symbol": "TSLA", "start": "2025-07-01", "end": "2025-06-01"},
    )
    assert res.status_code == 400


def test_run_prep_scores_aggregates_and_caches(client, session, monkeypatch):
    monkeypatch.setattr(prep_service.news_client, "fetch_news", lambda *a, **k: fake_articles())
    monkeypatch.setattr(prep_service.scorer, "score_headlines", fake_score_headlines)
    run = seed_run(session)

    prep_service.run_prep(session, run)

    assert run.status == "done"
    assert run.metrics["n_articles"] == 3
    assert run.metrics["n_days_covered"] == 2  # June 2 and June 4
    assert run.metrics["first_day"] == "2025-06-02"
    # Progress went through the phases.
    phases = [p["phase"] for p in run.progress]
    assert phases[0] == "fetching" and "scoring" in phases and phases[-1] == "aggregating"

    # Headlines are now scored and browsable through the endpoint.
    rows = client.get("/api/v1/sentiment/headlines", params={"symbol": "TSLA"}).json()
    assert len(rows) == 3
    beat = next(r for r in rows if "beats" in r["headline"])
    assert beat["pos"] == 0.9

    # Coverage reflects the per-day aggregates (June 2: 0.9-0.05 vs 0.05-0.9 -> net 0).
    cov = client.get("/api/v1/sentiment/coverage", params={"symbol": "TSLA"}).json()
    assert cov["days_with_news"] == 2
    june2 = next(d for d in cov["daily"] if d["day"] == "2025-06-02")
    assert abs(june2["net"]) < 1e-9 and june2["count"] == 2

    # Daily aggregates landed in feature_cache under the finbert set.
    from sqlalchemy import select

    from models import FeatureCache

    cached = (
        session.execute(
            select(FeatureCache).where(FeatureCache.feature_set == prep_service.FEATURE_SET)
        )
        .scalars()
        .all()
    )
    assert {c.ts.date().isoformat() for c in cached} == {"2025-06-02", "2025-06-04"}


def test_run_prep_skips_already_scored_articles(client, session, monkeypatch):
    monkeypatch.setattr(prep_service.news_client, "fetch_news", lambda *a, **k: fake_articles())
    score_calls = []

    def counting_scorer(headlines):
        score_calls.append(list(headlines))
        return fake_score_headlines(headlines)

    monkeypatch.setattr(prep_service.scorer, "score_headlines", counting_scorer)

    run1 = seed_run(session)
    prep_service.run_prep(session, run1)
    first_scored = sum(len(c) for c in score_calls)

    run2 = seed_run(session)
    prep_service.run_prep(session, run2)

    # Second run found everything scored already — FinBERT did no extra work,
    # and the dedupe kept the corpus at three rows.
    assert sum(len(c) for c in score_calls) == first_scored
    assert run2.status == "done"
    from sqlalchemy import func, select

    n_rows = session.execute(select(func.count()).select_from(NewsArticle)).scalar_one()
    assert n_rows == 3


def test_headlines_empty_for_unknown_symbol(client):
    assert client.get("/api/v1/sentiment/headlines", params={"symbol": "NOPE"}).json() == []
