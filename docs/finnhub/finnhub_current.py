

# export FINNHUB_API_KEY="your_api_key_here"



import os
import finnhub

# Initialize the client with your API key
# It's best practice to use environment variables
API_KEY = os.environ.get("FINNHUB_API_KEY", "YOUR_ACTUAL_API_KEY")

finnhub_client = finnhub.Client(api_key=API_KEY)

def get_stock_quote(symbol):
    try:
        # Fetch the quote data
        quote = finnhub_client.quote(symbol)
        
        print(f"--- {symbol.upper()} Stock Data ---")
        print(f"Current Price: ${quote['c']}")
        print(f"High Price of the day: ${quote['h']}")
        print(f"Low Price of the day: ${quote['l']}")
        print(f"Open Price of the day: ${quote['o']}")
        print(f"Previous Close Price: ${quote['pc']}")
        print(f"Change: {quote['d']} ({quote['dp']}%)")
    except finnhub.FinnhubAPIException as e:
        print(f"API Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Example: Apple Inc.
    get_stock_quote("AAPL")