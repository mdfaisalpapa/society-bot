from flask import Flask, request
import os
from conversation.engine import ConversationEngine

app = Flask(__name__)
engine = ConversationEngine()

# Get your token from your environment
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 

@app.route('/', methods=['POST'])
def test_webhook():
    update = request.get_json()
    print(f"DEBUG: Received update: {update}")
    
    if update:
        try:
            # Process synchronously like your old script, NO THREADING
            engine.process_update(update)
        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}")
            
    return "OK", 200

if __name__ == '__main__':
    # Keep host 0.0.0.0 and port 8085 for Nginx
    app.run(host='0.0.0.0', port=8085, debug=True)