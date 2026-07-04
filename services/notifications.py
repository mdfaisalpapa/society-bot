import logging
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
