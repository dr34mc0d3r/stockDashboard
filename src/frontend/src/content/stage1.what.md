## What We're Doing

This first stage **gathers the raw material** for everything that follows. You pick a
stock **symbol**, a **start** and **end** date, and a **timeframe**, and the backend
downloads that history from Alpaca and stores it in our MariaDB database.

Each row we store is one **OHLCV bar** — the Open, High, Low, Close, and Volume for one
time interval (a minute, hour, or day). A chart is just a sequence of these bars.

Data you download is **kept**, so every later Lab stage reads from the database instead
of re-downloading. The table below the form shows everything already stored.
