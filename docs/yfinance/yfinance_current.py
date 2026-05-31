import yfinance as yf

def get_current_ohlcv(symbol):
    print(f"Fetching data for {symbol.upper()}...")
    
    ticker = yf.Ticker(symbol)
    
    # 1. Get the latest 1-minute OHLC prices
    df = ticker.history(period="1d", interval="5m")
    if df.empty:
        print(f"No pricing data returned for {symbol}.")
        return

    latest_bar = df.iloc[-1]
    
    # 2. Extract live cumulative day volume using fast_info
    # This avoids the 1-minute bar volume sync lag
    live_volume = ticker.fast_info.get('last_volume', 0)
    if live_volume == 0 and 'Volume' in latest_bar:
        live_volume = latest_bar['Volume']

    print(f"\n--- {symbol.upper()} Live OHLCV Snapshot ---")
    print(f"Open:              ${latest_bar['Open']:.2f}")
    print(f"High:              ${latest_bar['High']:.2f}")
    print(f"Low:               ${latest_bar['Low']:.2f}")
    print(f"Close (Last Price):${latest_bar['Close']:.2f}")
    print(f"Total Day Volume:  {int(live_volume):,}") # Pretty printed with commas

if __name__ == "__main__":
    get_current_ohlcv("TSLA")