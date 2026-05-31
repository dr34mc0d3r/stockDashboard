import os
from pathlib import Path

from dotenv import load_dotenv

# Credentials live in src/.env (one level up from this package).
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# Origins allowed to call this API from the browser. Defaults cover the
# common React dev servers (Vite on 5173, Create React App on 3000).
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
]
