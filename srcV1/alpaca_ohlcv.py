import os
import time
import json
from typing import cast
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
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

def fetch_live_ohlcv(symbol: str):
    print(f"Monitoring live 1-minute OHLCV data for {symbol} (Output: JSON)...\n")
    
    last_printed_timestamp = None
    
    while True:
        try:
            now = datetime.now(timezone.utc)
            start_time = now - timedelta(minutes=5)
            
            request_params = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=cast(TimeFrame, TimeFrame.Minute),
                start=start_time,
                feed=DataFeed.IEX
            )

            bars = cast(BarSet, client.get_stock_bars(request_params))
            bars_df = bars.df
            
            if not bars_df.empty:
                latest_bar = bars_df.iloc[-1]
                latest_timestamp = bars_df.index[-1][1]
                
                # Only output if a new minute bar has generated or updated
                if latest_timestamp != last_printed_timestamp:
                    
                    # Construct a structured dictionary
                    ohlcv_payload = {
                        "symbol": symbol,
                        "timestamp": latest_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        "data": {
                            "open": float(latest_bar['open']),
                            "high": float(latest_bar['high']),
                            "low": float(latest_bar['low']),
                            "close": float(latest_bar['close']),
                            "volume": int(latest_bar['volume'])
                        }
                    }
                    
                    # Convert to minified or pretty-printed JSON string
                    json_output = json.dumps(ohlcv_payload, indent=2)
                    print(json_output)
                    
                    last_printed_timestamp = latest_timestamp
                    
        except Exception as e:
            # Output errors as JSON as well for structured logging
            error_payload = {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
            print(json.dumps(error_payload))
            
        time.sleep(10)

if __name__ == "__main__":
    TARGET_SYMBOL = "AAPL" 
    fetch_live_ohlcv(TARGET_SYMBOL)