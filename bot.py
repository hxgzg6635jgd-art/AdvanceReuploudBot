import os
import asyncio
from starlette.applications import Starlette
from starlette.responses import Response, PlainTextResponse
from starlette.routing import Route
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ["BOT_TOKEN"]
URL = os.environ["RENDER_EXTERNAL_URL"]
PORT = int(os.getenv("PORT", 8000))

# बॉट बनाएं
bot_app = Application.builder().token(TOKEN).updater(None).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("बॉट चालू है! ✅")

bot_app.add_handler(CommandHandler("start", start))

# वेबहुक हैंडलर
async def webhook(request):
    update = Update.de_json(await request.json(), bot_app.bot)
    await bot_app.update_queue.put(update)
    return Response()

async def health(request):
    return PlainTextResponse("ok")

# वेबहुक सेट करें और सर्वर चलाएं
async def main():
    await bot_app.bot.set_webhook(f"{URL}/webhook")
    
    starlette_app = Starlette(routes=[
        Route("/webhook", webhook, methods=["POST"]),
        Route("/healthcheck", health, methods=["GET"]),
    ])
    
    import uvicorn
    config = uvicorn.Config(app=starlette_app, host="0.0.0.0", port=PORT)
    server = uvicorn.Server(config)
    
    async with bot_app:
        await bot_app.start()
        await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
