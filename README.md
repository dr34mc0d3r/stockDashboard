# Stock Dashboard

A full-stack application for visualizing stock market OHLCV (Open, High, Low, Close, Volume) data and calculating real-time technical indicators.

## Architecture

- **Backend**: FastAPI (Python)
  - Manages data ingestion using `alpaca-py`.
  - Provides a modular service layer for calculating technical indicators (e.g., Parkinson Volatility, Acceleration, Money Flow Ratio, VWAP Z-Score).
  - Exposes REST endpoints for historical data and a WebSocket stream for real-time updates.
- **Frontend**: React (Vite, TailwindCSS)
  - Interactive UI for querying historical data by symbol, timeframe, and date range.
  - Visualization powered by `lightweight-charts`.
  - Configurable technical indicator selection with detailed documentation and mathematical insights built into the UI.

## Project Status

The application currently supports:
- Fetching and charting historical OHLCV data.
- Selecting and visualizing multiple technical indicators.
- Real-time websocket data streaming.
- Educational insights regarding indicator mechanics and calculation methods.
