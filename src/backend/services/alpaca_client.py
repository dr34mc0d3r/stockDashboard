import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

import certifi

from config import ALPACA_API_KEY, ALPACA_SECRET_KEY

# Verify TLS against certifi's CA bundle. The interpreter on the headless
# Ubuntu host has no system trust store wired into Python's default OpenSSL
# context, which surfaces as CERTIFICATE_VERIFY_FAILED when reaching Alpaca.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Map friendly timeframe strings to Alpaca's raw query values.
TIMEFRAME_MAP = {
    "1m": "1Min",
    "5m": "5Min",
    "1h": "1Hour",
    "1d": "1Day",
}

BASE_URL = "https://data.alpaca.markets/v2/stocks/bars"


class AlpacaError(Exception):
    """Raised when the upstream Alpaca request cannot be completed."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def fetch_historical_ohlcv(
    symbol: str, timeframe: str, start: str, end: str
) -> dict:
    """Fetch historical OHLCV bars from Alpaca and return a clean payload.

    Dates are ISO strings ('YYYY-MM-DD' or RFC3339). Raises AlpacaError on
    any upstream failure so the caller can translate it into an HTTP response.
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise AlpacaError("Alpaca API credentials are not configured.", status_code=500)

    query_params = {
        "symbols": symbol.upper(),
        "timeframe": TIMEFRAME_MAP[timeframe],
        "start": start,
        "end": end,
        "feed": "iex",  # Compatible with free-tier credentials.
    }
    full_url = f"{BASE_URL}?{urllib.parse.urlencode(query_params)}"
    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }
    req = urllib.request.Request(full_url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, context=SSL_CONTEXT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else str(e)
        raise AlpacaError(f"Alpaca request failed ({e.code}): {body}", status_code=502)
    except urllib.error.URLError as e:
        raise AlpacaError(f"Could not reach Alpaca: {e.reason}", status_code=502)

    raw_bars = payload.get("bars", {}).get(symbol.upper(), [])
    bars = [
        {
            "timestamp": bar.get("t"),
            "open": float(bar.get("o")),
            "high": float(bar.get("h")),
            "low": float(bar.get("l")),
            "close": float(bar.get("c")),
            "volume": int(bar.get("v")),
        }
        for bar in raw_bars
    ]

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "start": start,
        "end": end,
        "results_count": len(bars),
        "bars": bars,
    }
