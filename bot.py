import os, asyncio, logging
from starlette.applications import Starlette
from starlette.responses import Response, PlainTextResponse
from starlette.requests import Request
from starlette.routing import Route
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

# ✅ ये तीनों VARIABLES Render खुद से देगा - कॉपी करते वक्त ध्यान रखें
TOKEN = os.environ["BOT_TOKEN"]
URL   = os.environ["RENDER_EXTERNAL_URL"]
PORT  = int(os.getenv("PORT", 8000))

# लॉगिंग सेट करें
logging.basicConfig(level=logging.INFO)

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """जब भी कोई मैसेज आए, ये फंक्शन चलेगा"""
    chat_id = update.effective_chat.id
    text = update.message.text
    await update.message.reply_text(f"आपने लिखा: {text}")

async def main():
    # बॉट एप्लिकेशन बनाएं
    app = Application.builder().token(TOKEN).updater(None).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # वेबहुक सेट करें (यही वो मैजिक है जो कन्फ्लिक्ट से बचाता है)
    await app.bot.set_webhook(f"{URL}/telegram")
    
    async def telegram(request: Request) -> Response:
        await app.update_queue.put(Update.de_json(await request.json(), app.bot))
        return Response()
    
    async def health(_: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")
    
    # वेब सर्वर बनाएं
    starlette = Starlette(routes=[
        Route("/telegram", telegram, methods=["POST"]),
        Route("/healthcheck", health, methods=["GET"]),
    ])
    
    import uvicorn
    config = uvicorn.Config(app=starlette, host="0.0.0.0", port=PORT)
    server = uvicorn.Server(config)
    
    async with app:
        await app.start()
        await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
