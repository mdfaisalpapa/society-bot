"""Configuration management for Society Bot"""
import os
from dotenv import load_dotenv
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")
ERPNEXT_URL = os.getenv("ERPNEXT_URL", "").rstrip('/')
ERPNEXT_API_KEY = os.getenv("ERPNEXT_API_KEY")
ERPNEXT_API_SECRET = os.getenv("ERPNEXT_API_SECRET")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
DATABASE_PATH = os.getenv("DATABASE_PATH", "database/sessions.db")
DATABASE_DIR = os.path.dirname(DATABASE_PATH)
os.makedirs(DATABASE_DIR, exist_ok=True)
TENANT_WIZARD_STATES = {"NAME": 1, "RELATIONSHIP": 2, "MOBILE": 3, "EMAIL": 4, "START_DATE": 5, "END_DATE": 6, "CONFIRM": 7}
PET_WIZARD_STATES = {"NAME": 1, "LICENSE_NO": 2, "LICENSE_ISSUE": 3, "LICENSE_EXPIRY": 4, "VAX_CERT": 5, "VAX_DATE": 6, "VAX_DUE": 7, "CONFIRM": 8}
PAGINATION_LIMIT = 5
MAX_FILE_SIZE_MB = 10
ALLOWED_FILE_TYPES = ["image/jpeg", "image/png", "application/pdf", "image/webp"]
MODULE_FILE_LIMITS = {"Maintenance Ticket": 3, "Visitor Log": 1, "Customer": 5}
API_TIMEOUT = 10
REQUEST_TIMEOUT = 30
