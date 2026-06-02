"""Alpaca historical-bars REST client with pagination.

Alpaca caps each ``/v2/stocks/bars`` response at ~10k bars and returns a
``next_page_token`` when more data exists. V1 ignored that token and silently
truncated large pulls; here we loop until the token is exhausted.
"""

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import certifi

from config import ALPACA_API_KEY, ALPACA_SECRET_KEY

# Verify TLS against certifi's CA bundle (headless hosts may lack a system
# trust store wired into Python's default OpenSSL context).
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

TIMEFRAME_MAP = {
    "1m": "1Min",
    "5m": "5Min",
    "1h": "1Hour",
    "1d": "1Day",
}

BASE_URL = "https://data.alpaca.markets/v2/stocks/bars"
PAGE_LIMIT = 10000  # Alpaca max bars per page.


class AlpacaError(Exception):
    """Raised when the upstream Alpaca request cannot be completed."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _parse_ts(value: str) -> datetime:
    """Parse an RFC3339 timestamp ('...Z') into a naive UTC datetime."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(tz=None).replace(tzinfo=None) if dt.tzinfo else dt


def fetch_bars(symbol: str, timeframe: str, start: str, end: str) -> list[dict]:
    """Fetch every historical bar for the range, following pagination.

    Returns a list of dicts: {ts(datetime), open, high, low, close, volume}.
    Raises AlpacaError on any upstream failure.
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise AlpacaError("Alpaca API credentials are not configured.", status_code=500)
    if timeframe not in TIMEFRAME_MAP:
        raise AlpacaError(f"Invalid timeframe '{timeframe}'.", status_code=400)

    sym = symbol.upper()
    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }

    bars: list[dict] = []
    page_token: str | None = None

    while True:
        params = {
            "symbols": sym,
            "timeframe": TIMEFRAME_MAP[timeframe],
            "start": start,
            "end": end,
            "limit": PAGE_LIMIT,
            "feed": "iex",  # Free-tier compatible.
            "sort": "asc",
        }
        if page_token:
            params["page_token"] = page_token

        url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, context=SSL_CONTEXT) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else str(e)
            raise AlpacaError(f"Alpaca request failed ({e.code}): {body}", status_code=502)
        except urllib.error.URLError as e:
            raise AlpacaError(f"Could not reach Alpaca: {e.reason}", status_code=502)

        for bar in payload.get("bars", {}).get(sym, []):
            bars.append(
                {
                    "ts": _parse_ts(bar["t"]),
                    "open": float(bar["o"]),
                    "high": float(bar["h"]),
                    "low": float(bar["l"]),
                    "close": float(bar["c"]),
                    "volume": int(bar["v"]),
                }
            )

        page_token = payload.get("next_page_token")
        if not page_token:
            break

    return bars
