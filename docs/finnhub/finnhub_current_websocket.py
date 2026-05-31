import os
import json
import websocket

API_KEY = os.environ.get("FINNHUB_API_KEY", "YOUR_ACTUAL_API_KEY")

def on_message(ws, message):
    data = json.loads(message)
    # Check if the message contains trade data
    if data.get("type") == "trade":
        for trade in data["data"]:
            symbol = trade["s"]
            price = trade["p"]
            volume = trade["v"]
            # Timestamp is in milliseconds
            timestamp = trade["t"] 
            print(f"[{symbol}] Price: ${price:.2f} | Volume: {volume}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("### Connection Closed ###")

def on_open(ws):
    # Subscribe to the stocks you want to track live
    # Note: Free tier accounts generally have access to US major equities (e.g., AAPL, AMZN)
    ws.send('{"type":"subscribe","symbol":"AAPL"}')
    # ws.send('{"type":"subscribe","symbol":"BINANCE:BTCUSDT"}') # Crypto works too!

if __name__ == "__main__":
    # Enable debug formatting if you want to see raw socket traffic
    # websocket.enableTrace(True)
    
    socket_url = f"wss://ws.finnhub.io?token={API_KEY}"
    
    ws = websocket.WebSocketApp(
        socket_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    ws.on_open = on_open
    
    print("Connecting to Finnhub live stream...")
    ws.run_forever()