import os
import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# कॉन्फ़िगरेशन
TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = f"https://advanceeuploadbot-7.onrender.com/webhook"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# बॉट अप्लिकेशन
app = Application.builder().token(TOKEN).build()

# हैंडलर
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ बॉट चालू है! मुझे कुछ भी मैसेज भेजें, मैं जवाब दूंगा।")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"आपने कहा: {update.message.text}")

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# वेबहुक हैंडलर
async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500)

async def health(request):
    return web.Response(text="OK", status=200)

# मेन फंक्शन
async def main():
    # वेबहुक सेट करें
    await app.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"✅ Webhook set to: {WEBHOOK_URL}")
    
    # सर्वर शुरू करें
    runner = web.AppRunner(web.Application())
    await runner.setup()
    
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    runner.app.router.add_post("/webhook", handle_webhook)
    runner.app.router.add_get("/health", health)
    
    await site.start()
    logger.info(f"🤖 Bot running on port {PORT}")
    
    # हमेशा के लिए चलाएं
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
