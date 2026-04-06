import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
TOKEN = os.environ.get("BOT_TOKEN", "")

# Telegram API URL
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}"

def send_message(chat_id, text):
    """Telegram में मैसेज भेजें"""
    url = f"{TELEGRAM_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    try:
        response = requests.post(url, json=data)
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram से आने वाले अपडेट यहाँ आएंगे"""
    try:
        data = request.get_json()
        
        # चैट ID और मैसेज लें
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")
            
            # /start कमांड हैंडल करें
            if text == "/start":
                send_message(chat_id, "✅ Bot is alive! Send /menu to see options.")
            elif text == "/menu":
                send_message(chat_id, "📋 Menu:\n/set_channel - Set channel\n/set_time - Set time\n/status - Check status")
            elif text == "/status":
                send_message(chat_id, "✅ Bot is running normally!")
            else:
                send_message(chat_id, f"You said: {text}")
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/health', methods=['GET'])
def health():
    """Render के health check के लिए"""
    return "OK", 200

@app.route('/', methods=['GET'])
def home():
    return "Bot is running!", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print(f"🚀 Starting bot on port {port}")
    app.run(host='0.0.0.0', port=port)
