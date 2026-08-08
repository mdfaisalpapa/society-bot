import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Telegram Group IDs
OWNERS_GROUP = os.getenv("OWNERS_GROUP_ID")
RESIDENTS_GROUP = os.getenv("RESIDENTS_GROUP_ID")

# ERPNext Configuration
FRAPPE_URL = os.getenv("ERPNEXT_URL")
FRAPPE_API_KEY = os.getenv("ERPNEXT_API_KEY")
FRAPPE_API_SECRET = os.getenv("ERPNEXT_API_SECRET")