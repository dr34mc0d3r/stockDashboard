"""Alpaca News REST client (Stage 4).

Same shape as services/alpaca_client.py — same credentials, same auth headers,
same ``next_page_token`` pagination loop — pointed at the news endpoint.
Headlines only (``include_content=false``): FinBERT scores the headline text,
and article bodies would bloat both the response and the lesson.
"""

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import certifi

from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
from services.alpaca_client import AlpacaError

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
PAGE_LIMIT = 50  # Alpaca max news items per page.


def _parse_ts(value: str) -> datetime:
    """Parse an RFC3339 timestamp ('...Z') into a naive UTC datetime."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(tz=None).replace(tzinfo=None) if dt.tzinfo else dt


def fetch_news(symbol: str, start: str, end: str, max_articles: int = 500) -> list[dict]:
    """Fetch headlines for ``symbol`` in [start, end], following pagination.

    Returns a list of dicts {id, ts(datetime), headline, source, url}, capped
    at ``max_articles`` (the "small corpus" guard — FinBERT on this CPU costs
    ~0.1–0.3s per headline). De-dupes by Alpaca's stable article id.
    Raises AlpacaError on any upstream failure.
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise AlpacaError("Alpaca API credentials are not configured.", status_code=500)

    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }

    articles: list[dict] = []
    seen: set[str] = set()
    page_token: str | None = None

    while len(articles) < max_articles:
        params = {
            "symbols": symbol,
            "start": start,
            "end": end,
            "limit": min(PAGE_LIMIT, max_articles - len(articles)),
            "include_content": "false",
            "sort": "asc",
        }
        if page_token:
            params["page_token"] = page_token

        url = f"{NEWS_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, context=SSL_CONTEXT) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else str(e)
            raise AlpacaError(
                f"Alpaca news request failed ({e.code}): {body}", status_code=502
            ) from e
        except urllib.error.URLError as e:
            raise AlpacaError(f"Could not reach Alpaca: {e.reason}", status_code=502) from e

        for item in payload.get("news", []):
            article_id = str(item.get("id", ""))
            headline = (item.get("headline") or "").strip()
            if not article_id or not headline or article_id in seen:
                continue
            seen.add(article_id)
            articles.append(
                {
                    "id": article_id,
                    "ts": _parse_ts(item["created_at"]),
                    "headline": headline[:512],
                    "source": (item.get("source") or "")[:64],
                    "url": item.get("url") or "",
                }
            )
            if len(articles) >= max_articles:
                break

        page_token = payload.get("next_page_token")
        if not page_token:
            break

    return articles
