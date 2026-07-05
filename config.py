import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Admin Chat ID
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "YOUR_PERSONAL_CHAT_ID_HERE")

# ERPNext Configuration
FRAPPE_URL = os.getenv("ERPNEXT_URL")
FRAPPE_API_KEY = os.getenv("ERPNEXT_API_KEY")
FRAPPE_API_SECRET = os.getenv("ERPNEXT_API_SECRET")