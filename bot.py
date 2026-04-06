import os
import asyncio
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

TOKEN = os.environ["BOT_TOKEN"]
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

# Webhook सेट करने के लिए
WEBHOOK_URL = f"https://{os.environ['RENDER_EXTERNAL_URL'].split('//')[1]}/webhook"

# HTTP सर्वर हैंडलर
class WebhookHandler(BaseHTTPRequestHandler):
    async def handle_updates(self, data):
        try:
            update = Update.de_json(data, bot.bot)
            await bot.update_queue.put(update)
        except Exception as e:
            print(f"Error: {e}")
    
    def do_POST(self):
        if self.path == '/webhook':
            content_length = int(self.headers['Content-Length'])
            post_data = json.loads(self.rfile.read(content_length))
            
            # Async handle करें
            asyncio.create_task(self.handle_updates(post_data))
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
    
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # logs को साफ रखने के लिए

async def main():
    # Webhook सेट करें
    await bot.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook set to: {WEBHOOK_URL}")
    
    # HTTP सर्वर शुरू करें
    server = HTTPServer(('0.0.0.0', PORT), WebhookHandler)
    
    async with bot:
        await bot.start()
        print(f"🤬 बॉट चल रहा है on port {PORT}")
        
        # अलग थ्रेड में सर्वर चलाएं
        import threading
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        
        # हमेशा के लिए चलाएं
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
