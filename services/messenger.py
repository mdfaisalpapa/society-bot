import json
import requests
from services.telegram import TelegramService
from utils.logger import app_logger  # Added logger import

class Messenger:
    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Safely escapes Telegram Markdown characters to prevent 400 Bad Request errors.
        Use this when injecting variables like emails, names, or addresses into strings.
        """
        if not text:
            return ""
        # Characters that Telegram's Markdown parser trips over if unclosed
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        safe_text = str(text)
        for char in escape_chars:
            safe_text = safe_text.replace(char, f"\\{char}")
        return safe_text

    @staticmethod
    def get_file_url(platform: str, file_id: str) -> str:
        if platform == "telegram":
            return TelegramService.get_file_url(file_id)
        elif platform == "whatsapp":
            # You can easily add WhatsApp logic here later
            return None
        return None
    
    @staticmethod
    def send(platform: str, user_id: str, text: str, **kwargs):
        """
        The universal sender. Routes generic commands to the correct platform.
        """
        if platform == "telegram":
            # 1. Get the markup dictionary
            telegram_markup = Messenger._format_for_telegram(**kwargs)
            
            # 2. Pass the dictionary DIRECTLY to TelegramService
            # (Do NOT use json.dumps here, as telegram.py already does it!)
            try:
                response = TelegramService.send_message(user_id, text, telegram_markup)
                # If TelegramService returns the requests.Response object, check for errors:
                if response and hasattr(response, 'status_code') and response.status_code != 200:
                    app_logger.error(f"Telegram API Error [{response.status_code}]: {response.text}")
            except Exception as e:
                app_logger.error(f"Messenger Send Error: {e}")
            
        elif platform == "whatsapp":
            pass
        else:
            app_logger.error(f"❌ Messenger Error: Unknown platform '{platform}'")

    @staticmethod
    def _format_for_telegram(**kwargs) -> dict:
        """Translates generic UI requests into Telegram's JSON structure."""
        markup = {}
        
        # 1. Translate a generic Grid into an Inline Keyboard
        if "inline_keyboard" in kwargs:
            markup["inline_keyboard"] = kwargs["inline_keyboard"]
        if "grid" in kwargs:
            inline_keyboard = []
            for row in kwargs["grid"]:
                telegram_row = []
                for button in row:
                    for text_label, data in button.items():
                        telegram_row.append({"text": text_label, "callback_data": data})
                inline_keyboard.append(telegram_row)
            markup["inline_keyboard"] = inline_keyboard

        # 2. Translate a simple Force Reply
        if kwargs.get("force_reply"):
            markup["force_reply"] = True

        # 3. Translate a native Contact Request
        if "request_contact" in kwargs:
            button_text = kwargs["request_contact"]
            markup["keyboard"] = [[{"text": button_text, "request_contact": True}]]
            markup["one_time_keyboard"] = True
            markup["resize_keyboard"] = True

        # 4. Translate a Remove Keyboard command
        if kwargs.get("remove_keyboard"):
            markup["remove_keyboard"] = True

        # Return None if no UI elements were requested so the API doesn't complain
        return markup if markup else None

    @staticmethod
    def send_photo(platform: str, chat_id: str, photo_bytes: bytes, caption: str = "", **kwargs):
        """Universally routes photo messages with optional UI elements."""
        if platform == "telegram":
            telegram_markup = Messenger._format_for_telegram(**kwargs)
            try:
                response = TelegramService.send_photo(chat_id, photo_bytes, caption, telegram_markup)
                if response and hasattr(response, 'status_code') and response.status_code != 200:
                    app_logger.error(f"Telegram API Error (Photo) [{response.status_code}]: {response.text}")
            except Exception as e:
                app_logger.error(f"Messenger Send Photo Error: {e}")
            
        elif platform == "whatsapp":
            pass
        else:
            app_logger.error(f"❌ Messenger Error: Unknown platform '{platform}'")

    @staticmethod
    def kick_user_from_group(chat_id: str, group_id: str):
        """Removes a user from a specific group. They can rejoin later if permitted."""
        import os
        import requests
        
        bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        base_url = f"https://api.telegram.org/bot{bot_token}"
        
        # 1. Ban them (Removes them from the group)
        res_ban = requests.post(f"{base_url}/banChatMember", json={"chat_id": group_id, "user_id": chat_id})
        if res_ban.status_code != 200:
             app_logger.error(f"Failed to ban user {chat_id} from {group_id}: {res_ban.text}")
        
        # 2. Immediately Unban them (So they aren't blacklisted forever)
        res_unban = requests.post(f"{base_url}/unbanChatMember", json={"chat_id": group_id, "user_id": chat_id})
        if res_unban.status_code != 200:
             app_logger.error(f"Failed to unban user {chat_id} from {group_id}: {res_unban.text}")

    @staticmethod
    def send_ntfy(topic: str, title: str = "Society Bot Alert", message: str = ""):
        """Sends a push notification to a specific, secure topic."""
        if not topic:
            return # Failsafe if the user hasn't opted in
            
        try:
            import requests
            ntfy_url = f"https://ntfy.sh/{topic}"
            headers = {"Title": title, "Priority": "high", "Tags": "rotating_light"}
            
            res = requests.post(ntfy_url, data=message.encode('utf-8'), headers=headers, timeout=5)
            if res.status_code != 200:
                app_logger.error(f"Ntfy Push Failed [{res.status_code}]: {res.text}")
        except Exception as e:
            from utils.logger import app_logger
            app_logger.error(f"Ntfy Push Failed for topic {topic}: {e}")