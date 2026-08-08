import json
import requests
from services.telegram import TelegramService

class Messenger:
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
            TelegramService.send_message(user_id, text, telegram_markup)
            
        elif platform == "whatsapp":
            pass
        else:
            print(f"❌ Messenger Error: Unknown platform '{platform}'")

    @staticmethod
    def _format_for_telegram(**kwargs) -> dict:
        """Translates generic UI requests into Telegram's JSON structure."""
        markup = {}
        
        # 1. Translate a generic Grid into an Inline Keyboard
        # Example input: grid=[[{"Button": "/command"}]]
        if "inline_keyboard" in kwargs:
            markup["inline_keyboard"] = kwargs["inline_keyboard"]
        if "grid" in kwargs:
            inline_keyboard = []
            for row in kwargs["grid"]:
                telegram_row = []
                for button in row:
                    for text, data in button.items():
                        telegram_row.append({"text": text, "callback_data": data})
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
            # 1. Get the markup dictionary using your existing translator
            telegram_markup = Messenger._format_for_telegram(**kwargs)
            
            # 2. Pass the dictionary DIRECTLY to TelegramService
            TelegramService.send_photo(chat_id, photo_bytes, caption, telegram_markup)
            
        elif platform == "whatsapp":
            # Ready for future WhatsApp implementation
            pass
        else:
            print(f"❌ Messenger Error: Unknown platform '{platform}'")


    @staticmethod
    def kick_user_from_group(chat_id: str, group_id: str):
        """Removes a user from a specific group. They can rejoin later if permitted."""
        import os
        import requests
        
        bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        base_url = f"https://api.telegram.org/bot{bot_token}"
        
        # 1. Ban them (Removes them from the group)
        requests.post(f"{base_url}/banChatMember", json={"chat_id": group_id, "user_id": chat_id})
        
        # 2. Immediately Unban them (So they aren't blacklisted forever)
        requests.post(f"{base_url}/unbanChatMember", json={"chat_id": group_id, "user_id": chat_id})



    @staticmethod
    def send_ntfy(topic: str, title: str = "Society Bot Alert", message: str = ""):
        """Sends a push notification to a specific, secure topic."""
        if not topic:
            return # Failsafe if the user hasn't opted in
            
        try:
            import requests
            ntfy_url = f"https://ntfy.sh/{topic}"
            headers = {"Title": title, "Priority": "high", "Tags": "rotating_light"}
            
            requests.post(ntfy_url, data=message.encode('utf-8'), headers=headers, timeout=5)
        except Exception as e:
            from utils.logger import app_logger
            app_logger.error(f"Ntfy Push Failed for topic {topic}: {e}")

    