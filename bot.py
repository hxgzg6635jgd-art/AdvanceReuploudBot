import os
import asyncio
import logging
from starlette.applications import Starlette
from starlette.responses import Response, PlainTextResponse
from starlette.requests import Request
from starlette.routing import Route
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ✅ Render अपने आप ये वेरिएबल देता है
TOKEN = os.environ["BOT_TOKEN"]
URL = os.environ["RENDER_EXTERNAL_URL"]
PORT = int(os.getenv("PORT", 8000))

# लॉगिंग सेट करें (एरर ट्रैक करने के लिए)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----- यहाँ अपने कमांड हैंडलर लिखें -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start कमांड का रिप्लाई"""
    await update.message.reply_text("✅ बॉट ऑनलाइन है! मैं आपका मैसेज रिप्लाई कर सकता हूँ।")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """बिना कमांड वाले मैसेज का जवाब"""
    user_message = update.message.text
    await update.message.reply_text(f"आपने लिखा: {user_message}")

# ----- मेन फंक्शन - वेबहुक सेटअप -----
async def main():
    # अप्लिकेशन बनाएं (updater=None बहुत जरूरी है!)
    application = Application.builder().token(TOKEN).updater(None).build()

    # हैंडलर रजिस्टर करें
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # वेबहुक सेट करें - यहीं से Telegram को पता चलता है कि अपडेट कहाँ भेजने हैं
    webhook_url = f"{URL}/telegram"
    await application.bot.set_webhook(webhook_url, allowed_updates=Update.ALL_TYPES)
    logger.info(f"✅ वेबहुक सेट हो गया: {webhook_url}")

    # वेब सर्वर बनाएं
    async def telegram_webhook(request: Request) -> Response:
        """Telegram से आने वाले अपडेट यहाँ आएंगे"""
        try:
            data = await request.json()
            update = Update.de_json(data, application.bot)
            await application.update_queue.put(update)
            return Response()
        except Exception as e:
            logger.error(f"वेबहुक एरर: {e}")
            return Response(status_code=500)

    async def health_check(request: Request) -> PlainTextResponse:
        """Render के Health Check के लिए - 200 OK लौटाना जरूरी है"""
        return PlainTextResponse("ok")

    starlette_app = Starlette(routes=[
        Route("/telegram", telegram_webhook, methods=["POST"]),
        Route("/healthcheck", health_check, methods=["GET"]),
    ])

    # सर्वर कॉन्फ़िगर करें
    server = uvicorn.Server(
        uvicorn.Config(
            app=starlette_app,
            host="0.0.0.0",  # 127.0.0.1 नहीं लिखना - Render पर काम नहीं करेगा
            port=PORT,
            use_colors=False,
        )
    )

    # बॉट और सर्वर एक साथ चलाएँ
    async with application:
        await application.start()
        logger.info(f"🤬 बॉट शुरू हो गया! URL: {URL}")
        await server.serve()
        await application.stop()

if __name__ == "__main__":
    asyncio.run(main())
