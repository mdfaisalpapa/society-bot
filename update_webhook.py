import requests
import os
from dotenv import load_dotenv

# 👇 ADD THIS LINE to actually read the .env file!
load_dotenv() 

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = "https://bot.railwayofficersclub.in/" 

api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"

payload = {
    "url": WEBHOOK_URL,
    "allowed_updates": ["message", "callback_query", "chat_join_request"] 
}

response = requests.post(api_url, json=payload)
print(response.json())