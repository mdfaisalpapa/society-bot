import os
import requests
import json
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_API_URL

class TelegramService:
    @staticmethod
    def send_message(chat_id: str, text: str, reply_markup: dict = None):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
            
        try:
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
        except Exception as e:
            print(f"Telegram API Error: {e}")

    @staticmethod
    def answer_callback_query(callback_query_id: str):
        """Tells Telegram the inline button click was received to stop the loading icon."""
        try:
            requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": callback_query_id})
        except Exception as e:
            pass
   
    def get_file_url(file_id: str) -> str:
        # Use the variable from config.py
        api_url = f"{TELEGRAM_API_URL}/getFile?file_id={file_id}"
        
        response = requests.get(api_url).json()
        
        if response.get("ok"):
            file_path = response["result"]["file_path"]
            # Return full download URL
            return f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        
        return None
    @staticmethod
    def send_photo(chat_id: str, photo_bytes: bytes, caption: str = "", reply_markup: dict = None):
        """Sends a raw byte array as a photo to Telegram with optional markup."""
        
        # 1. Use the official Telegram API URL from your config
        url = f"{TELEGRAM_API_URL}/sendPhoto"
        
        # 2. Telegram requires files to be sent as multipart/form-data
        files = {"photo": ("gatepass.png", photo_bytes, "image/png")}
        
        # 3. Construct the data payload
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "Markdown"
        }
        
        # 4. Attach the translated inline keyboard if it exists
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        
        # 5. Post to Telegram
        try:
            response = requests.post(url, files=files, data=data)
            if response.status_code != 200:
                print(f"DEBUG Telegram Photo Error: {response.text}")
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram API Error: {e}")
            return False