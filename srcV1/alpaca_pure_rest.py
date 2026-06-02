import os
import json
import urllib.request
import urllib.parse
import urllib.error
from dotenv import load_dotenv

# Load API credentials from .env file
load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

if not API_KEY or not SECRET_KEY:
    raise ValueError("API Credentials missing. Please check your .env file.")

# Map user choices to raw Alpaca query parameters 
TIMEFRAME_MAP = {
    "1m": "1Min",
    "5m": "5Min",
    "1h": "1Hour",
    "1d": "1Day"
}

def get_historical_ohlcv_rest(symbol: str, timeframe: str, start_date: str, end_date: str):
    if timeframe not in TIMEFRAME_MAP:
        raise ValueError(f"Invalid timeframe. Choose from: {list(TIMEFRAME_MAP.keys())}")
    
    # Alpaca's Multi-bar V2 endpoint URL
    base_url = "https://data.alpaca.markets/v2/stocks/bars"
    
    # Define query parameters
    query_params = {
        "symbols": symbol.upper(),
        "timeframe": TIMEFRAME_MAP[timeframe],
        "start": start_date,  # Format: YYYY-MM-DD or RFC3339 string
        "end": end_date,
        "feed": "iex"         # Ensures compatibility with Free Tier credentials
    }
    
    # Encode variables securely into a URL string (?symbols=AAPL&timeframe=5Min...)
    url_encoded_params = urllib.parse.urlencode(query_params)
    full_url = f"{base_url}?{url_encoded_params}"
    
    # Construct raw HTTP headers
    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY
    }
    
    # Create the Request object
    req = urllib.request.Request(full_url, headers=headers, method="GET")
    
    try:
        # Open connection and read response
        with urllib.request.urlopen(req) as response:
            raw_data = response.read().decode('utf-8')
            alpaca_json = json.loads(raw_data)
            
            # Extract bars for our requested token
            raw_bars = alpaca_json.get("bars", {}).get(symbol.upper(), [])
            
            # Map Alpaca's short keys back to clear human-readable properties
            formatted_bars = []
            for bar in raw_bars:
                formatted_bars.append({
                    "timestamp": bar.get("t"), # Time
                    "open": float(bar.get("o")),
                    "high": float(bar.get("h")),
                    "low": float(bar.get("l")),
                    "close": float(bar.get("c")),
                    "volume": int(bar.get("v"))
                })
            
            # Package into unified clean JSON payload
            output = {
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "start": start_date,
                "end": end_date,
                "results_count": len(formatted_bars),
                "bars": formatted_bars
            }
            
            print(json.dumps(output, indent=2))
            
    except urllib.error.HTTPError as e:
        # Parse error response strings directly from server body if available
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        error_payload = {
            "error": "HTTP Request Failed",
            "code": e.code,
            "details": error_body
        }
        print(json.dumps(error_payload, indent=2))
    except Exception as e:
        print(json.dumps({"error": f"An unexpected error occurred: {str(e)}"}, indent=2))

if __name__ == "__main__":
    # Test execution parameters
    get_historical_ohlcv_rest(
        symbol="AAPL", 
        timeframe="1h", 
        start_date="2026-05-15", 
        end_date="2026-05-20"
    )