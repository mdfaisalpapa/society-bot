import logging
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
