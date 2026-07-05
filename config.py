"""
config.py
Configuration settings for Society Bot

All deployment-specific settings are loaded from .env.
No hard-coded credentials should be stored here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ==========================================================
# Load Environment Variables
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

# ==========================================================
# Application
# ==========================================================

APP_NAME = "Society Bot"
APP_VERSION = "1.0.0"

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# ==========================================================
# ERPNext Configuration
# ==========================================================

ERPNEXT_URL = os.getenv("ERPNEXT_URL", "").rstrip("/")

ERPNEXT_API_KEY = os.getenv("ERPNEXT_API_KEY", "")

ERPNEXT_API_SECRET = os.getenv("ERPNEXT_API_SECRET", "")

VERIFY_SSL = os.getenv("VERIFY_SSL", "True").lower() == "true"

if not ERPNEXT_URL:
    raise ValueError("ERPNEXT_URL not configured")

if not ERPNEXT_API_KEY:
    raise ValueError("ERPNEXT_API_KEY not configured")

if not ERPNEXT_API_SECRET:
    raise ValueError("ERPNEXT_API_SECRET not configured")

# ==========================================================
# Telegram Configuration
# ==========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not configured")

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
)

TELEGRAM_FILE_API = (
    f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"
)

# ==========================================================
# Logging
# ==========================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "society_bot.log"

# ==========================================================
# SQLite Database
# ==========================================================

DATABASE_PATH = Path(
    os.getenv(
        "DATABASE_PATH",
        BASE_DIR / "database" / "sessions.db"
    )
)

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# ==========================================================
# HTTP Settings
# ==========================================================

HTTP_TIMEOUT = int(
    os.getenv("HTTP_TIMEOUT", "30")
)

CONNECT_TIMEOUT = int(
    os.getenv("CONNECT_TIMEOUT", "10")
)

READ_TIMEOUT = int(
    os.getenv("READ_TIMEOUT", "30")
)

REQUEST_TIMEOUT = (
    CONNECT_TIMEOUT,
    READ_TIMEOUT
)

# ==========================================================
# Retry Policy
# ==========================================================

API_RETRIES = int(
    os.getenv("API_RETRIES", "3")
)

API_BACKOFF = float(
    os.getenv("API_BACKOFF", "1")
)

# ==========================================================
# Pagination
# ==========================================================

PAGINATION_LIMIT = int(
    os.getenv("PAGINATION_LIMIT", "5")
)

# ==========================================================
# Session
# ==========================================================

SESSION_TIMEOUT_MINUTES = int(
    os.getenv("SESSION_TIMEOUT_MINUTES", "30")
)

# ==========================================================
# File Uploads
# ==========================================================

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE_MB = int(
    os.getenv("MAX_FILE_SIZE_MB", "25")
)

ALLOWED_FILE_TYPES = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf"
]

MODULE_FILE_LIMITS = {
    "Maintenance Ticket": 3,
    "Visitor Log": 1,
    "Customer": 5,
    "Resident Pet": 3,
    "Tenants": 5,
    "Vehicles": 3
}

# ==========================================================
# Scheduler
# ==========================================================

REMINDER_INTERVAL_MINUTES = int(
    os.getenv(
        "REMINDER_INTERVAL_MINUTES",
        "60"
    )
)

# ==========================================================
# Society
# ==========================================================

SOCIETY_NAME = os.getenv(
    "SOCIETY_NAME",
    "Kendriya Vihar Phase III"
)

DEFAULT_COUNTRY_CODE = "+91"

DATE_FORMAT = "%d-%m-%Y"

DATETIME_FORMAT = "%d-%m-%Y %H:%M:%S"

# ==========================================================
# Wizard States
# (Temporary - will move to constants.py later)
# ==========================================================

TENANT_WIZARD_STATES = {
    "NAME": 1,
    "RELATIONSHIP": 2,
    "MOBILE": 3,
    "EMAIL": 4,
    "START_DATE": 5,
    "END_DATE": 6,
    "CONFIRM": 7
}

PET_WIZARD_STATES = {
    "NAME": 1,
    "LICENSE_NO": 2,
    "LICENSE_ISSUE": 3,
    "LICENSE_EXPIRY": 4,
    "VAX_CERT": 5,
    "VAX_DATE": 6,
    "VAX_DUE": 7,
    "CONFIRM": 8
}
