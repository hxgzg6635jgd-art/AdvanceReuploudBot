import os
import asyncio
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ===== कॉन्फ़िगरेशन =====
TOKEN = os.environ["BOT_TOKEN"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"]
PORT = int(os.getenv("PORT", "10000"))  # ✅ 10000 को स्ट्रिंग से इंट में बदला

print(f"🚀 Starting bot on port: {PORT}")

# ===== बॉट बनाएं =====
bot = Application.builder().token(TOKEN).updater(None).build()

# ===== कमांड हैंडलर =====
async def start(update: Update, context):
    await update.message.reply_text("✅ बॉट चालू है! मुझे कोई भी मैसेज भेजें, मैं जवाब दूंगा।")

async def echo(update: Update, context):
    await update.message.reply_text(f"आपने कहा: {update.message.text}")

# हैंडलर रजिस्टर करें
bot.add_handler(CommandHandler("start", start))
bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# ===== वेबहुक URL =====
WEBHOOK_URL = f"{RENDER_URL}/webhook"
print(f"📡 Webhook URL will be: {WEBHOOK_URL}")

# ===== HTTP सर्वर =====
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/webhook':
            try:
                length = int(self.headers['Content-Length'])
                data = json.loads(self.rfile.read(length))
                asyncio.create_task(self.handle_update(data))
                self.send_response(200)
                self.end_headers()
            except Exception as e:
                print(f"POST Error: {e}")
                self.send_response(500)
                self.end_headers()
    
    async def handle_update(self, data):
        try:
            update = Update.de_json(data, bot.bot)
            await bot.update_queue.put(update)
        except Exception as e:
            print(f"Update Error: {e}")
    
    def do_GET(self):
        if self.path == '/health' or self.path == '/healthcheck':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
            print("✅ Health check passed")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

# ===== मेन फंक्शन =====
async def main():
    # वेबहुक सेट करें
    await bot.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook set: {WEBHOOK_URL}")
    
    # सर्वर शुरू करें
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"🤖 HTTP Server listening on port {PORT}")
    
    async with bot:
        await bot.start()
        print(f"✅ Bot started successfully!")
        
        # सर्वर को अलग थ्रेड में चलाएं
        import threading
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        print(f"🔄 Server thread started")
        
        # हमेशा के लिए चलाएं
        await asyncio.Event().wait()

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Telegram Bot Starting...")
    print(f"📡 Bot Token: {TOKEN[:10]}...")
    print(f"🌐 Render URL: {RENDER_URL}")
    print(f"🔌 Port: {PORT}")
    print("=" * 50)
    asyncio.run(main())
