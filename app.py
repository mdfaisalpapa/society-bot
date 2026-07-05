from flask import Flask, request
from conversation.engine import ConversationEngine

app = Flask(__name__)
engine = ConversationEngine()

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    update = request.json
    if update:
        engine.process_update(update)
    return "OK", 200

if __name__ == '__main__':
    # Run the Flask app on port 5000
    # Use ngrok (e.g., `ngrok http 5000`) to expose this to Telegram during testing
    app.run(port=5000, debug=True)