import os
import json
from typing import cast
from datetime import datetime
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed
from alpaca.data.models import BarSet

# Load API credentials from .env file
load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

if not API_KEY or not SECRET_KEY:
    raise ValueError("API Credentials missing. Please check your .env file.")

# Initialize the Alpaca Historical Data Client
client = StockHistoricalDataClient(api_key=API_KEY, secret_key=SECRET_KEY)

# Map human-readable strings to Alpaca's TimeFrame classes
TIMEFRAME_MAP = {
    "1m": cast(TimeFrame, TimeFrame.Minute),
    "5m": TimeFrame(5, cast(TimeFrameUnit, TimeFrameUnit.Minute)), # Custom 5-minute window
    "1h": cast(TimeFrame, TimeFrame.Hour),
    "1d": cast(TimeFrame, TimeFrame.Day)
}

def get_historical_ohlcv(symbol: str, timeframe_str: str, start_date: str, end_date: str):
    """
    Fetches historical OHLCV data and prints it as a formatted JSON array.
    Dates should be passed in ISO format: 'YYYY-MM-DD'
    """
    if timeframe_str not in TIMEFRAME_MAP:
        raise ValueError(f"Invalid timeframe '{timeframe_str}'. Choose from: {list(TIMEFRAME_MAP.keys())}")
        
    # Parse the string dates into datetime objects
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    
    # Configure request parameters
    request_params = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TIMEFRAME_MAP[timeframe_str],
        start=start_dt,
        end=end_dt,
        feed=DataFeed.IEX  # Keeps it compatible with the Free Tier
    )
    
    try:
        # Fetch data
        bars = cast(BarSet, client.get_stock_bars(request_params))
        bars_df = bars.df

        results = []

        if not bars_df.empty:
            # Iterate through the DataFrame rows and indices
            for index, row in bars_df.iterrows():
                # Alpaca uses a MultiIndex: (symbol, timestamp)
                timestamp = cast(tuple, index)[1]
                
                results.append({
                    "timestamp": timestamp.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close']),
                    "volume": int(row['volume'])
                })
                
        # Wrap everything into a single cohesive JSON payload
        output_payload = {
            "symbol": symbol,
            "timeframe": timeframe_str,
            "start": start_date,
            "end": end_date,
            "results_count": len(results),
            "bars": results
        }
        
        print(json.dumps(output_payload, indent=2))
        
    except Exception as e:
        error_payload = {"error": str(e), "status": "failed"}
        print(json.dumps(error_payload, indent=2))

if __name__ == "__main__":
    # Example Configuration: Change these parameters as needed
    TARGET_SYMBOL = "AAPL"
    TIMEFRAME = "5m"          # Options: "1m", "5m", "1h", "1d"
    START = "2026-05-01"      # YYYY-MM-DD
    END = "2026-05-05"        # YYYY-MM-DD
    
    get_historical_ohlcv(TARGET_SYMBOL, TIMEFRAME, START, END)