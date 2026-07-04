#!/usr/bin/env python3
"""
Automatic project structure generator for Society Bot
"""

import os

# Define all files and their content
FILES = {
    "requirements.txt": """python-telegram-bot[all]==20.3
python-dotenv==1.0.0
requests==2.31.0
aiofiles==23.2.1
APScheduler==3.10.4
""",

    ".env.example": """# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here

# ERPNext Configuration
ERPNEXT_URL=https://your-erpnext-instance.com
ERPNEXT_API_KEY=your_api_key
ERPNEXT_API_SECRET=your_api_secret

# Bot Configuration
ADMIN_CHAT_ID=your_admin_chat_id
LOG_LEVEL=INFO
DEBUG=False

# Database
DATABASE_PATH=database/sessions.db
""",

    ".gitignore": """# Environment
.env
.env.local
*.pyc
__pycache__/

# Database
database/
*.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Temp
temp_uploads/
*.log
""",

    "config.py": open("config.py", "r").read() if os.path.exists("config.py") else '''"""Configuration management for Society Bot"""
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
''',

    "erp_api.py": '''import logging
import json
from typing import Optional, Dict, List
import requests
from config import ERPNEXT_URL, ERPNEXT_API_KEY, ERPNEXT_API_SECRET, API_TIMEOUT
logger = logging.getLogger(__name__)
class ERPNextClient:
    def __init__(self, base_url=ERPNEXT_URL, api_key=ERPNEXT_API_KEY, api_secret=ERPNEXT_API_SECRET):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.auth = (api_key, api_secret)
        self.session.headers.update({"Content-Type": "application/json"})
    def _handle_error(self, response):
        try:
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error: {e}")
            return None
    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}/api/resource/{endpoint}"
        kwargs.setdefault('timeout', API_TIMEOUT)
        try:
            response = self.session.request(method, url, **kwargs)
            return self._handle_error(response)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    def get_doc(self, doctype, name):
        data = self._request("GET", f"{doctype}/{name}")
        return data.get("data") if data else None
    def get_list(self, doctype, filters=None, fields=None, limit=None, order_by=None, offset=0):
        params = {"fields": json.dumps(fields or ["name"]), "limit_page_length": limit or 20, "limit_start": offset}
        if filters:
            filter_list = [[k, "=", v] for k, v in filters.items()]
            params["filters"] = json.dumps(filter_list)
        if order_by:
            params["order_by"] = order_by
        data = self._request("GET", doctype, params=params)
        return data.get("data", []) if data else None
    def insert_doc(self, doctype, doc_data):
        doc_data["doctype"] = doctype
        payload = {"data": json.dumps(doc_data)}
        data = self._request("POST", doctype, json=payload)
        return data.get("data") if data else None
    def update_doc(self, doctype, name, doc_data):
        payload = {"data": json.dumps(doc_data)}
        data = self._request("PUT", f"{doctype}/{name}", json=payload)
        return data.get("data") if data else None
    def delete_doc(self, doctype, name):
        data = self._request("DELETE", f"{doctype}/{name}")
        return data is not None
    def check_exists(self, doctype, name):
        doc = self.get_doc(doctype, name)
        return doc is not None
erp_client = ERPNextClient()
''',

    "session.py": '''import sqlite3
import json
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from config import DATABASE_PATH
logger = logging.getLogger(__name__)
class SessionManager:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self._init_db()
    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS sessions (chat_id TEXT PRIMARY KEY, module TEXT, step TEXT, state_data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
                conn.execute("""CREATE TABLE IF NOT EXISTS user_data (chat_id TEXT PRIMARY KEY, customer_name TEXT, is_tenant INTEGER DEFAULT 0, is_guard INTEGER DEFAULT 0, user_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
                conn.commit()
        except Exception as e:
            logger.error(f"DB init failed: {e}")
    def create_session(self, chat_id, module, step):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT OR REPLACE INTO sessions (chat_id, module, step, state_data, updated_at) VALUES (?, ?, ?, ?, ?)", (str(chat_id), module, step, json.dumps({}), datetime.now()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Session creation failed: {e}")
            return False
    def get_session(self, chat_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM sessions WHERE chat_id = ?", (str(chat_id),))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Session retrieval failed: {e}")
            return None
    def set_session_value(self, chat_id, key, value):
        try:
            session = self.get_session(chat_id)
            if not session:
                return False
            state_data = json.loads(session.get('state_data', '{}'))
            state_data[key] = str(value)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE sessions SET state_data = ?, updated_at = ? WHERE chat_id = ?", (json.dumps(state_data), datetime.now(), str(chat_id)))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set session value: {e}")
            return False
    def get_session_value(self, chat_id, key):
        try:
            session = self.get_session(chat_id)
            if not session:
                return ""
            state_data = json.loads(session.get('state_data', '{}'))
            return state_data.get(key, "")
        except Exception as e:
            logger.error(f"Failed to get session value: {e}")
            return ""
    def set_session_step(self, chat_id, step):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE sessions SET step = ?, updated_at = ? WHERE chat_id = ?", (step, datetime.now(), str(chat_id)))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set session step: {e}")
            return False
    def clear_session(self, chat_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM sessions WHERE chat_id = ?", (str(chat_id),))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Session deletion failed: {e}")
            return False
    def set_user_data(self, chat_id, customer_name, is_tenant=False, is_guard=False, user_name=""):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT OR REPLACE INTO user_data (chat_id, customer_name, is_tenant, is_guard, user_name, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (str(chat_id), customer_name, int(is_tenant), int(is_guard), user_name, datetime.now()))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set user data: {e}")
            return False
    def get_user_data(self, chat_id):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM user_data WHERE chat_id = ?", (str(chat_id),))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get user data: {e}")
            return None
    def cleanup_old_sessions(self, days=7):
        try:
            cutoff = datetime.now() - timedelta(days=days)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0
session_manager = SessionManager()
''',

    "keyboards.py": '''from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
class Keyboards:
    @staticmethod
    def main_menu(is_guard=False, is_registered=False, user_name="", cust_name=""):
        if is_guard:
            message = "🛡️ *Security Dashboard*"
            buttons = [[InlineKeyboardButton("📝 Log Walk-in Visitor", callback_data="/gate")], [InlineKeyboardButton("🔑 Check Passcode", callback_data="/passcode")], [InlineKeyboardButton("🚪 Logout", callback_data="/logout")]]
        elif is_registered:
            message = f"🏠 *Welcome, {user_name}!*"
            buttons = [[InlineKeyboardButton("✉️ Invite Visitor", callback_data="/invite"), InlineKeyboardButton("📋 History", callback_data="/visitors")], [InlineKeyboardButton("🛠️ Ticket", callback_data="/ticket"), InlineKeyboardButton("🔍 My Tickets", callback_data="/tickets")], [InlineKeyboardButton("👤 Profile", callback_data="/profile"), InlineKeyboardButton("🏠 Tenant", callback_data="/tenant")], [InlineKeyboardButton("🐾 Pets", callback_data="/pet"), InlineKeyboardButton("📊 Dues", callback_data="/dues")], [InlineKeyboardButton("🚪 Logout", callback_data="/logout")]]
        else:
            message = "🏠 *Welcome to Resident Bot*"
            buttons = [[InlineKeyboardButton("📝 Register", callback_data="/register")]]
        return message, InlineKeyboardMarkup(buttons)
    @staticmethod
    def tenant_relationships():
        buttons = [[InlineKeyboardButton("🏠 Tenant", callback_data="REL:Tenant")], [InlineKeyboardButton("👷 Caretaker", callback_data="REL:Caretaker")], [InlineKeyboardButton("🏢 Company", callback_data="REL:Company Lease")], [InlineKeyboardButton("🏨 Guest House", callback_data="REL:Guest House")]]
        return InlineKeyboardMarkup(buttons)
    @staticmethod
    def confirm_buttons(confirm_callback="/confirm", edit_callback="/edit", cancel_callback="/cancel"):
        buttons = [[InlineKeyboardButton("✅ Confirm", callback_data=confirm_callback)], [InlineKeyboardButton("✏️ Edit", callback_data=edit_callback)], [InlineKeyboardButton("❌ Cancel", callback_data=cancel_callback)]]
        return InlineKeyboardMarkup(buttons)
    @staticmethod
    def pet_menu(has_pets=False):
        if has_pets:
            message = "🐾 *Pet Management*"
            buttons = [[InlineKeyboardButton("➕ Add", callback_data="/add_pet"), InlineKeyboardButton("✏️ Edit", callback_data="/edit_pet")], [InlineKeyboardButton("❌ Remove", callback_data="/remove_pet")]]
        else:
            message = "🐾 No pets registered"
            buttons = [[InlineKeyboardButton("➕ Add Pet", callback_data="/add_pet")]]
        return message, InlineKeyboardMarkup(buttons)
''',

    "handlers/__init__.py": '''from .tenant import TenantHandler
from .visitor import VisitorHandler
from .maintenance import MaintenanceHandler
__all__ = ['TenantHandler', 'VisitorHandler', 'MaintenanceHandler']
''',

    "handlers/tenant.py": '''import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from config import TENANT_WIZARD_STATES
from erp_api import erp_client
from session import session_manager
from keyboards import Keyboards
from services.notifications import send_message
logger = logging.getLogger(__name__)

class TenantHandler:
    def __init__(self):
        self.erp = erp_client
        self.session = session_manager
    def get_states(self):
        return TENANT_WIZARD_STATES
    async def start_wizard(self, update, context):
        chat_id = update.effective_chat.id
        await update.callback_query.answer()
        self.session.create_session(chat_id, "Tenant", "NAME")
        message = "🏠 *New Tenant*\\nStep 1/6: Enter *Name*"
        await update.callback_query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)
        return TENANT_WIZARD_STATES["NAME"]
    async def step_name(self, update, context):
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        self.session.set_session_value(chat_id, "tenant_name", text)
        self.session.set_session_step(chat_id, "RELATIONSHIP")
        message = "🏠 *New Tenant*\\nStep 2/6: Select *Relationship*"
        await update.message.reply_text(message, reply_markup=Keyboards.tenant_relationships(), parse_mode=ParseMode.MARKDOWN)
        return TENANT_WIZARD_STATES["RELATIONSHIP"]
    async def step_relationship(self, update, context):
        chat_id = update.effective_chat.id
        await update.callback_query.answer()
        data = update.callback_query.data
        if not data.startswith("REL:"):
            await update.callback_query.edit_message_text("Use buttons to select")
            return TENANT_WIZARD_STATES["RELATIONSHIP"]
        relationship = data[4:]
        self.session.set_session_value(chat_id, "relationship", relationship)
        self.session.set_session_step(chat_id, "MOBILE")
        await update.callback_query.edit_message_text("🏠 *New Tenant*\\nStep 3/6: Enter *Mobile*", parse_mode=ParseMode.MARKDOWN)
        return TENANT_WIZARD_STATES["MOBILE"]
    async def step_mobile(self, update, context):
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        self.session.set_session_value(chat_id, "mobile", text)
        self.session.set_session_step(chat_id, "EMAIL")
        await update.message.reply_text("🏠 *New Tenant*\\nStep 4/6: Enter *Email* (or NA)", parse_mode=ParseMode.MARKDOWN)
        return TENANT_WIZARD_STATES["EMAIL"]
    async def step_email(self, update, context):
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        self.session.set_session_value(chat_id, "email", text)
        self.session.set_session_step(chat_id, "START_DATE")
        await update.message.reply_text("🏠 *New Tenant*\\nStep 5/6: Start Date (YYYY-MM-DD)", parse_mode=ParseMode.MARKDOWN)
        return TENANT_WIZARD_STATES["START_DATE"]
    async def step_start_date(self, update, context):
        chat_id = update.effective_chat.id
        date = update.message.text.strip()
        if not self._is_valid_date(date):
            await update.message.reply_text("Invalid date. Use YYYY-MM-DD")
            return TENANT_WIZARD_STATES["START_DATE"]
        self.session.set_session_value(chat_id, "start_date", date)
        self.session.set_session_step(chat_id, "END_DATE")
        await update.message.reply_text("🏠 *New Tenant*\\nStep 6/6: End Date (YYYY-MM-DD or NA)", parse_mode=ParseMode.MARKDOWN)
        return TENANT_WIZARD_STATES["END_DATE"]
    async def step_end_date(self, update, context):
        chat_id = update.effective_chat.id
        date = update.message.text.strip()
        if date.upper() != "NA" and not self._is_valid_date(date):
            await update.message.reply_text("Invalid date")
            return TENANT_WIZARD_STATES["END_DATE"]
        self.session.set_session_value(chat_id, "end_date", date)
        await self.show_confirmation(update, chat_id)
        return TENANT_WIZARD_STATES["CONFIRM"]
    async def show_confirmation(self, update, chat_id):
        name = self.session.get_session_value(chat_id, "tenant_name")
        relationship = self.session.get_session_value(chat_id, "relationship")
        mobile = self.session.get_session_value(chat_id, "mobile")
        email = self.session.get_session_value(chat_id, "email")
        start_date = self.session.get_session_value(chat_id, "start_date")
        end_date = self.session.get_session_value(chat_id, "end_date")
        message = f"🏠 *Verify Details*\\n👤 {name}\\n👥 {relationship}\\n📱 {mobile}\\n📧 {email}\\n📅 {start_date} to {end_date}"
        buttons = [[InlineKeyboardButton("✅ Confirm", callback_data="/confirm_tenant")], [InlineKeyboardButton("❌ Cancel", callback_data="/cancel")]]
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN)
    async def confirm(self, update, context):
        chat_id = update.effective_chat.id
        await update.callback_query.answer()
        try:
            user_data = self.session.get_user_data(chat_id)
            if not user_data:
                await send_message(chat_id, "Not registered")
                return ConversationHandler.END
            customer_name = user_data['customer_name']
            tenant_data = {"active": 1, "tenant_name": self.session.get_session_value(chat_id, "tenant_name"), "relationship": self.session.get_session_value(chat_id, "relationship"), "mobile_no": self.session.get_session_value(chat_id, "mobile"), "email": self.session.get_session_value(chat_id, "email"), "start_date": self.session.get_session_value(chat_id, "start_date")}
            end_date = self.session.get_session_value(chat_id, "end_date")
            if end_date and end_date != "NA":
                tenant_data["end_date"] = end_date
            customer = self.erp.get_doc("Customer", customer_name)
            if not customer:
                await send_message(chat_id, "Error")
                return ConversationHandler.END
            if "custom_tenants" not in customer:
                customer["custom_tenants"] = []
            customer["custom_tenants"].append(tenant_data)
            self.erp.update_doc("Customer", customer_name, customer)
            await send_message(chat_id, "✅ Tenant added!")
            self.session.clear_session(chat_id)
        except Exception as e:
            await send_message(chat_id, f"Error: {str(e)}")
        return ConversationHandler.END
    async def cancel(self, update, context):
        chat_id = update.effective_chat.id
        await update.callback_query.answer()
        self.session.clear_session(chat_id)
        await send_message(chat_id, "Cancelled")
        return ConversationHandler.END
    @staticmethod
    def _is_valid_date(date_text):
        if len(date_text) != 10 or date_text[4] != "-" or date_text[7] != "-":
            return False
        try:
            year, month, day = int(date_text[:4]), int(date_text[5:7]), int(date_text[8:10])
            return 1 <= month <= 12 and 1 <= day <= 31
        except:
            return False
''',

    "handlers/visitor.py": '''import logging
from telegram import Update
from telegram.ext import ContextTypes
from erp_api import erp_client
from session import session_manager
from services.notifications import send_message
logger = logging.getLogger(__name__)

class VisitorHandler:
    def __init__(self):
        self.erp = erp_client
        self.session = session_manager
    async def invite_visitor(self, update, context):
        await update.callback_query.answer()
        await send_message(update.effective_chat.id, "Enter visitor name")
''',

    "handlers/maintenance.py": '''import logging
from telegram import Update
from telegram.ext import ContextTypes
from erp_api import erp_client
from session import session_manager
from services.notifications import send_message
logger = logging.getLogger(__name__)

class MaintenanceHandler:
    def __init__(self):
        self.erp = erp_client
        self.session = session_manager
    async def raise_ticket(self, update, context):
        await update.callback_query.answer()
        await send_message(update.effective_chat.id, "Describe your issue")
''',

    "services/__init__.py": '''from .notifications import send_message, notify_admin
from .utils import Utils
__all__ = ['send_message', 'notify_admin', 'Utils']
''',

    "services/notifications.py": '''import logging
from telegram import Bot
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
logger = logging.getLogger(__name__)
bot = Bot(token=TELEGRAM_BOT_TOKEN)

async def send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN, reply_markup=None):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
        return True
    except Exception as e:
        logger.error(f"Failed: {e}")
        return False

async def notify_admin(message):
    if not ADMIN_CHAT_ID:
        return False
    return await send_message(ADMIN_CHAT_ID, message, parse_mode=ParseMode.MARKDOWN)
''',

    "services/utils.py": '''import hashlib
from datetime import datetime, timedelta

class Utils:
    @staticmethod
    def is_valid_date(date_text):
        if len(date_text) != 10 or date_text[4] != "-" or date_text[7] != "-":
            return False
        try:
            year, month, day = int(date_text[:4]), int(date_text[5:7]), int(date_text[8:10])
            return 1 <= month <= 12 and 1 <= day <= 31
        except:
            return False
    
    @staticmethod
    def generate_passcode(chat_id, identifier=""):
        seed = f"{chat_id}{identifier}{datetime.now().date()}"
        hash_obj = hashlib.md5(seed.encode())
        return str(abs(int(hash_obj.hexdigest(), 16)))[:5]
    
    @staticmethod
    def parse_relative_date(date_str):
        date_str = date_str.lower().strip()
        today = datetime.now().date()
        if date_str == "today":
            return str(today)
        elif date_str == "tomorrow":
            return str(today + timedelta(days=1))
        return None
''',

    "bot.py": '''import logging
import sys
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters
from telegram.constants import ParseMode
from telegram import Update
from config import TELEGRAM_BOT_TOKEN, LOG_LEVEL, TENANT_WIZARD_STATES
from keyboards import Keyboards
from services.notifications import send_message
from session import session_manager
from erp_api import erp_client
from handlers.tenant import TenantHandler
from handlers.visitor import VisitorHandler
from handlers.maintenance import MaintenanceHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

tenant_handler = TenantHandler()
visitor_handler = VisitorHandler()
maintenance_handler = MaintenanceHandler()

async def start(update, context):
    chat_id = update.effective_chat.id
    customers = erp_client.get_list("Customer", filters={"custom_telegram_chat_id": str(chat_id)}, fields=["name"], limit=1)
    if customers:
        customer_name = customers[0]['name']
        customer = erp_client.get_doc("Customer", customer_name)
        session_manager.set_user_data(chat_id, customer_name, is_tenant=False, user_name=customer.get('custom_owner_name', 'User'))
        message, markup = Keyboards.main_menu(is_guard=False, is_registered=True, user_name=customer.get('custom_owner_name', 'User'), cust_name=customer_name)
    else:
        message, markup = Keyboards.main_menu(is_registered=False)
    await send_message(chat_id, message, reply_markup=markup)

async def register(update, context):
    await update.callback_query.answer()
    await send_message(update.effective_chat.id, "Enter your flat number (e.g., TC2-411)")
    context.user_data['registration_step'] = 'flat_number'

async def handle_registration(update, context):
    chat_id = update.effective_chat.id
    text = update.message.text.strip().upper()
    if context.user_data.get('registration_step') != 'flat_number':
        return
    if not erp_client.check_exists("Customer", text):
        await send_message(chat_id, "Flat not found")
        return
    customer = erp_client.get_doc("Customer", text)
    erp_client.update_doc("Customer", text, {"custom_telegram_chat_id": str(chat_id)})
    session_manager.set_user_data(chat_id, text, is_tenant=False, user_name=customer.get('custom_owner_name', 'User'))
    await send_message(chat_id, f"✅ Registered to {text}")
    message, markup = Keyboards.main_menu(is_guard=False, is_registered=True, user_name=customer.get('custom_owner_name', 'User'), cust_name=text)
    await send_message(chat_id, message, reply_markup=markup)
    context.user_data.clear()

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "/register":
        await register(update, context)

async def error_handler(update, context):
    logger.error(f"Error: {context.error}")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    tenant_states = tenant_handler.get_states()
    tenant_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(tenant_handler.start_wizard, pattern="^/add_tenant$")],
        states={
            tenant_states["NAME"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, tenant_handler.step_name)],
            tenant_states["RELATIONSHIP"]: [CallbackQueryHandler(tenant_handler.step_relationship, pattern="^REL:")],
            tenant_states["MOBILE"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, tenant_handler.step_mobile)],
            tenant_states["EMAIL"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, tenant_handler.step_email)],
            tenant_states["START_DATE"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, tenant_handler.step_start_date)],
            tenant_states["END_DATE"]: [MessageHandler(filters.TEXT & ~filters.COMMAND, tenant_handler.step_end_date)],
            tenant_states["CONFIRM"]: [CallbackQueryHandler(tenant_handler.confirm, pattern="^/confirm_tenant$")],
        },
        fallbacks=[CallbackQueryHandler(tenant_handler.cancel, pattern="^/cancel")]
    )
    app.add_handler(tenant_conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_registration))
    app.add_error_handler(error_handler)
    logger.info("Starting bot...")
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Stopped")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal: {e}")
        sys.exit(1)
''',

    "README.md": "# Society Bot - Telegram Bot for Property Management\n\n## Features\n\n- Tenant Management\n- Visitor Management  \n- Maintenance Tickets\n- Pet Registration\n\n## Installation\n\n```bash\ngit clone https://github.com/mdfaisalpapa/society-bot.git\ncd society-bot\npython -m venv venv\nsource venv/bin/activate\npip install -r requirements.txt\ncp .env.example .env\npython bot.py\n```\n\n## Configuration\n\nEdit `.env` with your settings.\n"
}

# Create directory structure
DIRECTORIES = [
    "handlers",
    "services",
    "database",
]

def create_structure():
    print("🚀 Setting up Society Bot project...")
    
    for directory in DIRECTORIES:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    for file_path, content in FILES.items():
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"✅ Created file: {file_path}")
    
    print("\n" + "="*60)
    print("✨ Project structure created successfully!")
    print("="*60)
    print("\nNext steps:")
    print("1. cd /path/to/society-bot")
    print("2. python -m venv venv")
    print("3. source venv/bin/activate  (Windows: venv\\Scripts\\activate)")
    print("4. pip install -r requirements.txt")
    print("5. cp .env.example .env")
    print("6. Edit .env with your credentials")
    print("7. python bot.py")
    print("\n")

if __name__ == "__main__":
    create_structure()
