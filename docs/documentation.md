# Stock Dashboard Project Documentation

A full-stack application providing stock OHLCV (Open, High, Low, Close, Volume) data and technical indicators.

## Directory Structure

```text
/
├── src/
│   ├── backend/         # FastAPI backend
│   │   ├── routers/     # API route definitions
│   │   ├── services/    # Business logic & data fetching
│   │   └── tests/       # Backend unit tests
│   └── frontend/        # React/Vite frontend
│       ├── components/  # Reusable UI components
│       └── pages/       # Application views
└── docs/                # Project documentation
```

## How To

### Getting Started

1.  **Backend**: Ensure you have Python installed. The project uses `uv` for dependency management.
2.  **Frontend**: The project uses `npm` for managing React frontend dependencies.

### Running the Application

*   **Backend**:
    ```bash
    cd src/backend
    uv run uvicorn main:app --reload
    ```
*   **Frontend**:
    ```bash
    cd src/frontend
    npm install
    npm run dev
    ```

## API Routes

### OHLCV Data

**`GET /api/ohlcv`**
Return historical OHLCV bars for a symbol over a date range.

*Parameters:*
- `symbol` (string): Ticker symbol (e.g., AAPL)
- `start` (string): Start date (YYYY-MM-DD)
- `end` (string): End date (YYYY-MM-DD)
- `timeframe` (string, optional): One of "1Min", "5Min", "15Min", "1H", "1D" (default: "1d")

### Indicators

**`GET /api/indicators/catalog`**
List every available indicator to build the UI dynamically.

**`GET /api/indicators`**
Compute requested indicators over OHLCV bars for a symbol.

*Parameters:*
- `symbol`, `start`, `end`, `timeframe`: (Same as `/api/ohlcv`)
- `period` (int, default: 14): Lookback window in bars.
- `include` (string, default: "all"): Comma-separated indicator keys or "all".

### Real-time Streaming

**`WS /api/stream`**
Proxy Alpaca's live market-data stream.

*Query Parameters:*
- `symbols` (string, optional): Comma-separated symbols (e.g., AAPL,MSFT)
- `channels` (string, optional): Comma-separated channels (e.g., bars,trades)
