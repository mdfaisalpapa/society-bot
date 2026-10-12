import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

# Configuration
BOT_TOKEN = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
QRT_GROUP_ID = os.getenv("QRT_GROUP_ID")
ERP_BASE_URL = os.getenv("ERP_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("ERP_API_KEY")
API_SECRET = os.getenv("ERP_API_SECRET")

headers = {
    "Authorization": f"token {API_KEY}:{API_SECRET}",
    "Content-Type": "application/json"
}

def fetch_open_tickets():
    """Fetches all tickets currently active in the system."""
    url = f"{ERP_BASE_URL}/api/resource/Maintenance Ticket"
    
    status_criteria = ["Open", "Assigned", "Pending", "In Progress"]
    params = {
        "filters": json.dumps([["status", "in", status_criteria]]),
        "fields": json.dumps(["name", "category", "creation", "status", "resident"]),
        "limit_page_length": 0  # 0 fetches all matching records
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("data", [])
    except Exception as e:
        print(f"Failed to fetch tickets: {e}")
    return []

def send_to_telegram(text: str):
    """Pushes the formatted text to the QRT group."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": QRT_GROUP_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def main():
    if not QRT_GROUP_ID or not BOT_TOKEN:
        print("Error: Missing Telegram credentials or QRT_GROUP_ID in .env")
        return

    tickets = fetch_open_tickets()
    
    if not tickets:
        msg = "✅ *Daily Snag List*\n\nThere are currently *0* active maintenance tickets. Great job team!"
        send_to_telegram(msg)
        return

    category_tallies = {}
    escalated_tickets = []
    now = datetime.now()

    # Process and tally the tickets
    for t in tickets:
        cat = t.get("category", "Other")
        category_tallies[cat] = category_tallies.get(cat, 0) + 1
        
        creation_str = t.get("creation")
        if creation_str:
            # ERPNext outputs format: "YYYY-MM-DD HH:MM:SS.mmmmmm"
            try:
                creation_date = datetime.strptime(creation_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                if (now - creation_date) > timedelta(hours=24):
                    escalated_tickets.append(f"🎫 `{t['name']}` (Flat {t['resident']}) - {cat}")
            except ValueError:
                pass

    # Build the Telegram output
    msg = "📋 *Daily Maintenance Snag List*\n\n"
    msg += "*Active Tickets by Category:*\n"
    for cat, count in category_tallies.items():
        msg += f"🔹 {cat}: *{count}*\n"
    
    if escalated_tickets:
        msg += "\n🚨 *Overdue Tickets (> 24 Hours):*\n"
        for esc in escalated_tickets:
            msg += f"• {esc}\n"
    
    msg += "\n_Please check your individual bot chats to update assignments._"
    
    send_to_telegram(msg)

if __name__ == "__main__":
    main()
