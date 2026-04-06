import os
import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===== कॉन्फ़िगरेशन =====
TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.getenv("PORT", 10000))
DB_PATH = "bot_data.db"

# ===== डेटाबेस सेटअप =====
def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            chat_id INTEGER,
            text TEXT,
            media_type TEXT,
            file_id TEXT,
            created_at TIMESTAMP,
            delete_at TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('source_channel', 'None')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('delete_after_seconds', '3600')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('repost_enabled', 'True')")
    conn.commit()
    conn.close()
    print("✅ Database ready")

def get_setting(key):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    if result:
        value = result[0]
        if value == "None":
            return None
        elif value == "True":
            return True
        elif value == "False":
            return False
        elif key == "delete_after_seconds":
            return int(value)
        elif key == "source_channel" and value and value != "None":
            try:
                return int(value)
            except:
                return value
        return value
    return None

def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
        (key, str(value), datetime.now())
    )
    conn.commit()
    conn.close()

def save_post(message_id, chat_id, text, media_type=None, file_id=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    delete_at = datetime.now() + timedelta(seconds=get_setting("delete_after_seconds"))
    cursor.execute('''
        INSERT INTO posts (message_id, chat_id, text, media_type, file_id, created_at, delete_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (message_id, chat_id, text, media_type, file_id, datetime.now(), delete_at))
    conn.commit()
    conn.close()

def update_post_status(message_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE posts SET status = ? WHERE message_id = ?", (status, message_id))
    conn.commit()
    conn.close()

def get_last_post():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT message_id, chat_id, text, media_type, file_id FROM posts WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
    )
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            "message_id": result[0],
            "chat_id": result[1],
            "text": result[2],
            "media_type": result[3],
            "file_id": result[4]
        }
    return None

def get_all_active_posts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT message_id, chat_id, text, media_type, file_id, delete_at FROM posts WHERE status = 'active'")
    results = cursor.fetchall()
    conn.close()
    posts = []
    for result in results:
        posts.append({
            "message_id": result[0],
            "chat_id": result[1],
            "text": result[2],
            "media_type": result[3],
            "file_id": result[4],
            "delete_at": datetime.fromisoformat(result[5]) if isinstance(result[5], str) else result[5]
        })
    return posts

init_database()

# ===== बॉट बनाएं =====
bot = Application.builder().token(TOKEN).build()

# ===== मेन मेनू =====
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None):
    if chat_id is None:
        chat_id = update.effective_chat.id
    
    source_channel = get_setting("source_channel")
    delete_time = get_setting("delete_after_seconds")
    repost_enabled = get_setting("repost_enabled")
    
    keyboard = [
        [InlineKeyboardButton("📢 Set Channel", callback_data="set_channel")],
        [InlineKeyboardButton("⏰ Set Time", callback_data="set_time")],
        [InlineKeyboardButton("🔄 Toggle Repost", callback_data="toggle_repost")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🗑️ Clear Posts", callback_data="clear_posts")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""
🤖 *Bot Control Panel*

📢 *Channel:* `{source_channel if source_channel else 'Not set'}`
⏰ *Time:* {delete_time} seconds ({round(delete_time/3600, 1)} hours)
🔄 *Repost:* {'✅ ON' if repost_enabled else '❌ OFF'}
📝 *Active Posts:* {len(get_all_active_posts())}
"""
    await context.bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Bot started! Type /menu to open control panel.")
    await main_menu(update, context)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await main_menu(update, context)

# ===== कॉलबैक हैंडलर =====
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "set_channel":
        context.user_data["awaiting_channel"] = True
        await query.edit_message_text(
            "📢 *Set Channel*\n\nSend your channel @username or ID:\nExample: @my_channel or -1001234567890",
            parse_mode='Markdown'
        )
    
    elif data == "set_time":
        delete_time = get_setting("delete_after_seconds")
        keyboard = [
            [InlineKeyboardButton("1 hour", callback_data="time_3600")],
            [InlineKeyboardButton("6 hours", callback_data="time_21600")],
            [InlineKeyboardButton("12 hours", callback_data="time_43200")],
            [InlineKeyboardButton("24 hours", callback_data="time_86400")],
            [InlineKeyboardButton("2 days", callback_data="time_172800")],
            [InlineKeyboardButton("7 days", callback_data="time_604800")],
            [InlineKeyboardButton("🎯 Custom", callback_data="time_custom")],
            [InlineKeyboardButton("◀️ Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"⏰ Current: {delete_time}s\nChoose new time:", reply_markup=reply_markup)
    
    elif data.startswith("time_"):
        time_value = data.split("_")[1]
        if time_value == "custom":
            context.user_data["awaiting_custom_time"] = True
            await query.edit_message_text("🎯 Send time in seconds (eg: 3600)")
        else:
            seconds = int(time_value)
            set_setting("delete_after_seconds", seconds)
            await query.edit_message_text(f"✅ Time updated: {seconds}s")
            await asyncio.sleep(1)
            await main_menu(update, context, query.message.chat.id)
    
    elif data == "toggle_repost":
        current = get_setting("repost_enabled")
        new_value = not current
        set_setting("repost_enabled", new_value)
        await query.edit_message_text(f"🔄 Repost {'ON' if new_value else 'OFF'}")
        await asyncio.sleep(1)
        await main_menu(update, context, query.message.chat.id)
    
    elif data == "status":
        source_channel = get_setting("source_channel")
        delete_time = get_setting("delete_after_seconds")
        repost_enabled = get_setting("repost_enabled")
        active_posts = get_all_active_posts()
        text = f"📊 Channel: {source_channel}\n⏰ Time: {delete_time}s\n🔄 Repost: {'ON' if repost_enabled else 'OFF'}\n📝 Posts: {len(active_posts)}"
        await query.edit_message_text(text)
        await asyncio.sleep(2)
        await main_menu(update, context, query.message.chat.id)
    
    elif data == "clear_posts":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM posts WHERE status = 'active'")
        conn.commit()
        conn.close()
        await query.edit_message_text("🗑️ All posts cleared!")
        await asyncio.sleep(1)
        await main_menu(update, context, query.message.chat.id)
    
    elif data == "back":
        await main_menu(update, context, query.message.chat.id)
    
    elif data == "close":
        await query.edit_message_text("❌ Menu closed. Type /menu to open again.")

# ===== टेक्स्ट हैंडलर =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_chat.id
    
    if context.user_data.get("awaiting_channel"):
        context.user_data["awaiting_channel"] = False
        channel_input = text.strip()
        if channel_input.startswith("@"):
            try:
                chat = await bot.bot.get_chat(channel_input)
                channel_id = chat.id
            except:
                await update.message.reply_text("❌ Channel not found!")
                return
        else:
            try:
                channel_id = int(channel_input)
            except:
                await update.message.reply_text("❌ Invalid format!")
                return
        set_setting("source_channel", channel_id)
        await update.message.reply_text(f"✅ Channel set: `{channel_id}`", parse_mode='Markdown')
        await main_menu(update, context, user_id)
    
    elif context.user_data.get("awaiting_custom_time"):
        context.user_data["awaiting_custom_time"] = False
        try:
            seconds = int(text)
            if seconds <= 0:
                await update.message.reply_text("❌ Enter number greater than 0!")
                return
            set_setting("delete_after_seconds", seconds)
            await update.message.reply_text(f"✅ Time set: {seconds} seconds")
        except ValueError:
            await update.message.reply_text("❌ Please send a number!")
        await main_menu(update, context, user_id)

# ===== चैनल पोस्ट हैंडलर =====
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not get_setting("repost_enabled"):
        return
    
    source_channel = get_setting("source_channel")
    if source_channel is None:
        return
    
    if not update.channel_post:
        return
    
    if update.effective_chat.id != source_channel:
        return
    
    try:
        msg = update.channel_post
        msg_id = msg.message_id
        
        last = get_last_post()
        if last:
            try:
                await bot.bot.delete_message(last["chat_id"], last["message_id"])
                update_post_status(last["message_id"], "deleted")
            except:
                pass
        
        text = msg.text or msg.caption or ""
        media_type = None
        file_id = None
        
        if msg.photo:
            media_type = "photo"
            file_id = msg.photo[-1].file_id
        elif msg.video:
            media_type = "video"
            file_id = msg.video.file_id
        
        save_post(msg_id, source_channel, text, media_type, file_id)
        delay = get_setting("delete_after_seconds")
        asyncio.create_task(schedule_repost(msg_id, source_channel, text, media_type, file_id, delay))
        
    except Exception as e:
        print(f"Post error: {e}")

# ===== रिपोस्ट =====
async def schedule_repost(msg_id, chat_id, text, media_type, file_id, delay):
    await asyncio.sleep(delay)
    if not get_setting("repost_enabled"):
        return
    try:
        if media_type == "photo":
            await bot.bot.send_photo(chat_id, file_id, caption=text or None)
        elif media_type == "video":
            await bot.bot.send_video(chat_id, file_id, caption=text or None)
        else:
            await bot.bot.send_message(chat_id, text)
        update_post_status(msg_id, "reposted")
    except Exception as e:
        print(f"Repost error: {e}")

# ===== HTTP सर्वर हैंडलर (Webhook + Healthcheck) =====
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/webhook':
            try:
                length = int(self.headers['Content-Length'])
                data = json.loads(self.rfile.read(length))
                update = Update.de_json(data, bot.bot)
                asyncio.run_coroutine_threadsafe(
                    bot.update_queue.put(update),
                    asyncio.get_event_loop()
                )
                self.send_response(200)
                self.end_headers()
            except Exception as e:
                print(f"Webhook error: {e}")
                self.send_response(500)
                self.end_headers()
    
    def do_GET(self):
        # ✅ Healthcheck endpoint - Render के लिए जरूरी
        if self.path == '/health' or self.path == '/healthcheck':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

# ===== मेन =====
async def main():
    print("=" * 50)
    print("🤖 Bot Starting...")
    print("=" * 50)
    
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("menu", menu))
    bot.add_handler(CallbackQueryHandler(button_callback))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    bot.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    
    # Webhook सेट करें
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if render_url:
        webhook_url = f"{render_url}/webhook"
        await bot.bot.set_webhook(webhook_url)
        print(f"✅ Webhook set: {webhook_url}")
    
    # HTTP सर्वर शुरू करें
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    
    async with bot:
        await bot.start()
        print(f"✅ Bot started on port {PORT}")
        print(f"✅ Healthcheck: /healthcheck")
        
        import threading
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        
        print("🎉 Bot is ready!")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
