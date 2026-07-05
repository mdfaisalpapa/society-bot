import logging
import sys
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters
from telegram.constants import ParseMode
from telegram import Update
from config import TELEGRAM_BOT_TOKEN, LOG_LEVEL, TENANT_WIZARD_STATES
from services.keyboards import Keyboards
from services.notifications import send_message
from utils.session import session_manager
from api.erp import erp_client
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
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logger.info(f"Button clicked: {data}")  # ADD THIS LINE
    
    if data == "/register":
        await register(update, context)
    else:
        logger.warning(f"Unknown button: {data}")  # ADD THIS LINE
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
