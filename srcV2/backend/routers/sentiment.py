"""Stage 4 sentiment endpoints: the run-once prep job and corpus inspection.

`POST /sentiment/prepare` creates a TrainingRun row (stage="finbert-prep") and
spawns the background fetch→score→cache job; the frontend polls the run via
the existing `GET /runs/{id}`. The other two endpoints feed the headline
browser and the coverage timeline.
"""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from db import SessionDep
from models import NewsArticle, TrainingRun
from schemas import (
    CoverageDay,
    CoverageOut,
    HeadlineOut,
    SentimentPrepRequest,
    TrainingRunOut,
    normalize_symbol,
)
from services.sentiment.aggregate import daily_aggregate
from services.sentiment.prep_service import start_prep

router = APIRouter(prefix="/api/v1", tags=["sentiment"])


@router.post("/sentiment/prepare", response_model=TrainingRunOut)
def prepare_sentiment(req: SentimentPrepRequest, session: SessionDep) -> TrainingRun:
    """Kick off the corpus fetch + FinBERT scoring as a background job."""
    if req.start >= req.end:
        raise HTTPException(status_code=400, detail="start must be before end")

    run = TrainingRun(
        stage="finbert-prep",
        symbol=req.symbol,
        timeframe="1d",  # daily aggregates by convention
        start=req.start,
        end=req.end,
        status="queued",
        hyperparams={"max_articles": req.max_articles},
        progress=[],
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    start_prep(run.id)
    return run


@router.get("/sentiment/headlines", response_model=list[HeadlineOut])
def headlines(
    symbol: str,
    session: SessionDep,
    start: str | None = None,
    end: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[NewsArticle]:
    """The stored corpus for a symbol, newest first — scores included."""
    stmt = select(NewsArticle).where(NewsArticle.symbol == normalize_symbol(symbol))
    if start:
        stmt = stmt.where(NewsArticle.ts >= start)
    if end:
        stmt = stmt.where(NewsArticle.ts <= end)
    stmt = stmt.order_by(NewsArticle.ts.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


@router.get("/sentiment/coverage", response_model=CoverageOut)
def coverage(
    symbol: str,
    session: SessionDep,
    start: str | None = None,
    end: str | None = None,
) -> CoverageOut:
    """Per-day net sentiment + counts for the timeline and the slice check."""
    canonical = normalize_symbol(symbol)
    stmt = select(NewsArticle).where(NewsArticle.symbol == canonical, NewsArticle.pos.is_not(None))
    if start:
        stmt = stmt.where(NewsArticle.ts >= start)
    if end:
        stmt = stmt.where(NewsArticle.ts <= end)
    rows = session.execute(stmt).scalars().all()

    daily = daily_aggregate(
        [{"ts": r.ts, "pos": r.pos, "neg": r.neg, "neutral": r.neutral} for r in rows]
    )
    days = sorted(daily)
    return CoverageOut(
        symbol=canonical,
        days_with_news=len(days),
        first_day=days[0].isoformat() if days else None,
        last_day=days[-1].isoformat() if days else None,
        daily=[
            CoverageDay(day=d.isoformat(), count=daily[d]["count"], net=round(daily[d]["net"], 4))
            for d in days
        ],
    )
