import os
import asyncio
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = os.environ["BOT_TOKEN"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"]
PORT = int(os.getenv("PORT", 10000))

# बॉट बनाएं
bot = Application.builder().token(TOKEN).updater(None).build()

# कमांड हैंडलर
async def start(update: Update, context):
    await update.message.reply_text("✅ बॉट चालू है! मुझे कोई भी मैसेज भेजें।")

async def echo(update: Update, context):
    await update.message.reply_text(f"आपने कहा: {update.message.text}")

bot.add_handler(CommandHandler("start", start))
bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# वेबहुक URL
WEBHOOK_URL = f"{RENDER_URL}/webhook"

# HTTP हैंडलर
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/webhook':
            try:
                length = int(self.headers['Content-Length'])
                data = json.loads(self.rfile.read(length))
                # ✅ सही तरीके से async function call करें
                asyncio.run_coroutine_threadsafe(self.handle_update(data), loop)
                self.send_response(200)
                self.end_headers()
            except Exception as e:
                print(f"Error: {e}")
                self.send_response(500)
                self.end_headers()
    
    async def handle_update(self, data):
        try:
            update = Update.de_json(data, bot.bot)
            await bot.update_queue.put(update)
        except Exception as e:
            print(f"Update error: {e}")
    
    def do_GET(self):
        if self.path == '/health' or self.path == '/healthcheck':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

# ग्लोबल लूप
loop = None

async def main():
    global loop
    loop = asyncio.get_running_loop()
    
    # वेबहुक सेट करें
    await bot.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook set: {WEBHOOK_URL}")
    
    # सर्वर शुरू करें
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    
    async with bot:
        await bot.start()
        print(f"🤖 Bot started on port {PORT}")
        print(f"🌐 Webhook URL: {WEBHOOK_URL}")
        
        import threading
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        
        await asyncio.Event().wait()

if __name__ == "__main__":
    print("🚀 Starting bot...")
    asyncio.run(main())
