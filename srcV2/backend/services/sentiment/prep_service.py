"""The Stage 4 "run-once" prep job: fetch headlines → FinBERT → cache.

Runs as a background daemon thread (FinBERT on this CPU is ~0.1–0.3s per
headline) and reports through a TrainingRun row with stage="finbert-prep" —
the same status/progress/metrics machinery the trainers use, so the existing
polling UI and the startup orphan-recovery cover it for free.

Phases written to `progress`: fetching → scoring (per batch) → aggregating.
Final `metrics` hold the corpus stats the UI shows.
"""

from __future__ import annotations

import threading
import traceback
from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from db import SessionLocal
from models import FeatureCache, NewsArticle, TrainingRun
from services.sentiment import news_client, scorer
from services.sentiment.aggregate import daily_aggregate

# Daily aggregates live in feature_cache under this set, one row per calendar
# day (ts = midnight, timeframe "1d" by convention). Lag-free: the lag is
# applied at alignment time, so one cache serves any lag_days setting.
FEATURE_SET = "finbert_daily"
SCORE_BATCH = scorer.BATCH_SIZE


def _upsert_articles(session: Session, symbol: str, articles: list[dict]) -> int:
    """Insert fetched articles, skipping ids already stored (keeps any scores)."""
    existing = set(
        session.execute(select(NewsArticle.id).where(NewsArticle.symbol == symbol)).scalars()
    )
    new_rows = [NewsArticle(symbol=symbol, **a) for a in articles if a["id"] not in existing]
    session.add_all(new_rows)
    session.commit()
    return len(new_rows)


def _write_daily_cache(session: Session, symbol: str, daily: dict) -> None:
    """Replace this symbol's cached daily aggregates (delete + bulk insert)."""
    session.execute(
        sa_delete(FeatureCache).where(
            FeatureCache.symbol == symbol,
            FeatureCache.timeframe == "1d",
            FeatureCache.feature_set == FEATURE_SET,
        )
    )
    payloads = [
        {
            "symbol": symbol,
            "timeframe": "1d",
            "ts": datetime(day.year, day.month, day.day),
            "feature_set": FEATURE_SET,
            "payload": {"net": agg["net"], "count": agg["count"]},
        }
        for day, agg in sorted(daily.items())
    ]
    if payloads:
        session.execute(insert(FeatureCache), payloads)
    session.commit()


def run_prep(session: Session, run: TrainingRun) -> None:
    """The prep body, given an open session and its run row (testable directly)."""
    hp = run.hyperparams or {}
    symbol = run.symbol
    start, end = run.start, run.end
    max_articles = int(hp.get("max_articles", 300))
    progress: list[dict] = []

    def step(phase: str, **extra) -> None:
        progress.append({"phase": phase, **extra})
        run.progress = [*progress]  # new list: SQLAlchemy JSON dirty-tracking
        session.commit()

    # 1. Fetch headlines (paginated; capped — the "small corpus" guard).
    step("fetching", fetched=0, scored=0, total=0)
    articles = news_client.fetch_news(symbol, start, end, max_articles=max_articles)
    new_count = _upsert_articles(session, symbol, articles)
    step("fetched", fetched=len(articles), new=new_count, scored=0, total=len(articles))

    # 2. Score every still-unscored headline for this symbol/range with FinBERT.
    rows = list(
        session.execute(
            select(NewsArticle)
            .where(
                NewsArticle.symbol == symbol,
                NewsArticle.ts >= start,
                NewsArticle.ts <= end,
                NewsArticle.pos.is_(None),
            )
            .order_by(NewsArticle.ts.asc())
        ).scalars()
    )
    total = len(rows)
    for lo in range(0, total, SCORE_BATCH):
        batch = rows[lo : lo + SCORE_BATCH]
        scores = scorer.score_headlines([r.headline for r in batch])
        for row, s in zip(batch, scores):
            row.pos, row.neg, row.neutral = s["pos"], s["neg"], s["neutral"]
        session.commit()
        step("scoring", fetched=len(articles), scored=min(lo + SCORE_BATCH, total), total=total)

    # 3. Aggregate per day over ALL scored articles in range and cache.
    step("aggregating", fetched=len(articles), scored=total, total=total)
    scored = session.execute(
        select(NewsArticle).where(
            NewsArticle.symbol == symbol,
            NewsArticle.ts >= start,
            NewsArticle.ts <= end,
            NewsArticle.pos.is_not(None),
        )
    ).scalars()
    corpus = [{"ts": r.ts, "pos": r.pos, "neg": r.neg, "neutral": r.neutral} for r in scored]
    daily = daily_aggregate(corpus)
    _write_daily_cache(session, symbol, daily)

    nets = [agg["net"] for agg in daily.values()]
    run.metrics = {
        "n_articles": len(corpus),
        "n_days_covered": len(daily),
        "first_day": min(daily).isoformat() if daily else None,
        "last_day": max(daily).isoformat() if daily else None,
        "mean_net": round(sum(nets) / len(nets), 4) if nets else None,
        "pct_positive_days": round(sum(1 for v in nets if v > 0) / len(nets), 4) if nets else None,
        "feature_set": FEATURE_SET,
    }
    run.status = "done"
    session.commit()


def _prep(run_id: int) -> None:
    """DB-status wrapper around run_prep (executes in a worker thread)."""
    with SessionLocal() as session:
        run = session.get(TrainingRun, run_id)
        try:
            run.status = "running"
            session.commit()
            run_prep(session, run)
        except Exception as e:  # noqa: BLE001 — record any failure on the run row
            session.rollback()
            run = session.get(TrainingRun, run_id)
            run.status = "error"
            run.detail = f"{e}\n{traceback.format_exc()}"
            session.commit()


def start_prep(run_id: int) -> None:
    """Spawn the prep job in a daemon thread and return immediately."""
    threading.Thread(target=_prep, args=(run_id,), daemon=True).start()
