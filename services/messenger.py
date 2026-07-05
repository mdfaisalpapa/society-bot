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
            # Translate generic arguments into Telegram's specific JSON
            telegram_markup = Messenger._format_for_telegram(**kwargs)
            TelegramService.send_message(user_id, text, telegram_markup)
            
        elif platform == "whatsapp":
            # Placeholder: In the future, this will translate the exact same 
            # kwargs into WhatsApp's Interactive List format!
            pass
            
        else:
            print(f"❌ Messenger Error: Unknown platform '{platform}'")

    @staticmethod
    def _format_for_telegram(**kwargs) -> dict:
        """Translates generic UI requests into Telegram's JSON structure."""
        markup = {}
        
        # 1. Translate a generic Grid into an Inline Keyboard
        # Example input: grid=[[{"Button": "/command"}]]
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

    