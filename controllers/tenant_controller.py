import logging
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
        message = "🏠 *New Tenant*\nStep 1/6: Enter *Name*"
        await update.callback_query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)
        return TENANT_WIZARD_STATES["NAME"]
    async def step_name(self, update, context):
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        self.session.set_session_value(chat_id, "tenant_name", text)
        self.session.set_session_step(chat_id, "RELATIONSHIP")
        message = "🏠 *New Tenant*\nStep 2/6: Select *Relationship*"
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
        await update.callback_query.edit_message_text("🏠 *New Tenant*\nStep 3/6: Enter *Mobile*", parse_mode=ParseMode.MARKDOWN)
        return TENANT_WIZARD_STATES["MOBILE"]
    async def step_mobile(self, update, context):
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        self.session.set_session_value(chat_id, "mobile", text)
        self.session.set_session_step(chat_id, "EMAIL")
        await update.message.reply_text("🏠 *New Tenant*\nStep 4/6: Enter *Email* (or NA)", parse_mode=ParseMode.MARKDOWN)
        return TENANT_WIZARD_STATES["EMAIL"]
    async def step_email(self, update, context):
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        self.session.set_session_value(chat_id, "email", text)
        self.session.set_session_step(chat_id, "START_DATE")
        await update.message.reply_text("🏠 *New Tenant*\nStep 5/6: Start Date (YYYY-MM-DD)", parse_mode=ParseMode.MARKDOWN)
        return TENANT_WIZARD_STATES["START_DATE"]
    async def step_start_date(self, update, context):
        chat_id = update.effective_chat.id
        date = update.message.text.strip()
        if not self._is_valid_date(date):
            await update.message.reply_text("Invalid date. Use YYYY-MM-DD")
            return TENANT_WIZARD_STATES["START_DATE"]
        self.session.set_session_value(chat_id, "start_date", date)
        self.session.set_session_step(chat_id, "END_DATE")
        await update.message.reply_text("🏠 *New Tenant*\nStep 6/6: End Date (YYYY-MM-DD or NA)", parse_mode=ParseMode.MARKDOWN)
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
        message = f"🏠 *Verify Details*\n👤 {name}\n👥 {relationship}\n📱 {mobile}\n📧 {email}\n📅 {start_date} to {end_date}"
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
