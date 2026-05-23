"""Application configuration.

Loads from environment variables with .env file fallback.
All config is in English as per project convention.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

# --- Database ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{ROOT_DIR / 'cb_monitor.db'}",
)

# --- Tushare ---
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# --- Admin ---
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# --- Email (SendGrid) ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@cb-monitor.com")

# --- App ---
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
PORT = int(os.getenv("PORT", "8000"))

# --- Data Collection ---
COLLECTION_INTERVAL_HOURS = int(os.getenv("COLLECTION_INTERVAL_HOURS", "4"))

# --- User Agent for HTTP requests ---
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
