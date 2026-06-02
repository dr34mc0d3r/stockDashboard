"""Configuration for the Market ML Lab backend.

All secrets live in ``src/.env`` (one level up from this package) and are loaded
once at import time. Nothing here is committed — ``.env`` is gitignored.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL

# src/.env sits one directory above this package (src/backend/).
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

# --- Alpaca ---------------------------------------------------------------
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# --- MariaDB --------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "192.168.142.174")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "stock_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "stock_app")

# Built via URL.create so special characters in the password (?, ;, %, ...)
# are escaped correctly rather than corrupting the connection string.
DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)

# --- CORS -----------------------------------------------------------------
# Origins allowed to call this API from the browser (Vite dev server, etc.).
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
]
