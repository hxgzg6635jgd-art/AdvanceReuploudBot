import os
import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ===== कॉन्फ़िगरेशन =====
TOKEN = os.environ["BOT_TOKEN"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"]
PORT = int(os.getenv("PORT", 10000))
DB_PATH = "bot_data.db"

# ===== डेटाबेस सेटअप =====
def init_database():
    """डेटाबेस और टेबल बनाएं"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # सेटिंग्स टेबल
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # पोस्ट हिस्ट्री टेबल (कौन सी पोस्ट कब डिलीट/रिपोस्ट हुई)
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
    
    # डिफॉल्ट सेटिंग्स डालें (अगर मौजूद नहीं हैं)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('source_channel', 'None')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('delete_after_seconds', '3600')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('repost_enabled', 'True')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('last_post_id', 'None')")
    
    conn.commit()
    conn.close()
    print("✅ डेटाबेस इनिशियलाइज़ हो गया")

def get_setting(key):
    """सेटिंग वैल्यू लें"""
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
    """सेटिंग वैल्यू सेट करें"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
        (key, str(value), datetime.now())
    )
    conn.commit()
    conn.close()

def save_post(message_id, chat_id, text, media_type=None, file_id=None):
    """पोस्ट डेटाबेस में सेव करें"""
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
    """पोस्ट का स्टेटस अपडेट करें"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE posts SET status = ? WHERE message_id = ?",
        (status, message_id)
    )
    conn.commit()
    conn.close()

def get_last_post():
    """आखिरी पोस्ट लें"""
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
    """सभी एक्टिव पोस्ट लें"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT message_id, chat_id, text, media_type, file_id, delete_at FROM posts WHERE status = 'active'"
    )
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

# ===== डेटाबेस इनिशियलाइज़ करें =====
init_database()

# ===== बॉट बनाएं =====
bot = Application.builder().token(TOKEN).updater(None).build()

# ===== मेन मेनू =====
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None):
    """मेन मेनू दिखाएं"""
    if chat_id is None:
        chat_id = update.effective_chat.id
    
    # डेटाबेस से करंट सेटिंग्स लें
    source_channel = get_setting("source_channel")
    delete_time = get_setting("delete_after_seconds")
    repost_enabled = get_setting("repost_enabled")
    
    keyboard = [
        [InlineKeyboardButton("📢 चैनल सेट करें", callback_data="set_channel")],
        [InlineKeyboardButton("⏰ समय सेट करें", callback_data="set_time")],
        [InlineKeyboardButton("🔄 रिपोस्ट ऑन/ऑफ", callback_data="toggle_repost")],
        [InlineKeyboardButton("📊 स्टेटस देखें", callback_data="status")],
        [InlineKeyboardButton("🗑️ पुराने पोस्ट हटाएं", callback_data="clear_posts")],
        [InlineKeyboardButton("❌ बंद करें", callback_data="close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""
🤖 *बॉट कंट्रोल पैनल*

यहाँ से आप बॉट को कंट्रोल कर सकते हैं:

📢 *चैनल सेट करें* - कौन सा चैनल मॉनिटर करना है
⏰ *समय सेट करें* - पोस्ट कितने समय बाद डिलीट/रिपोस्ट होगी
🔄 *रिपोस्ट ऑन/ऑफ* - रिपोस्ट फीचर को चालू/बंद करें
📊 *स्टेटस देखें* - मौजूदा सेटिंग्स देखें

*मौजूदा सेटिंग्स (डेटाबेस से):*
• चैनल: `{source_channel if source_channel else '❌ सेट नहीं'}`
• समय: {delete_time} सेकंड ({round(delete_time/3600, 1)} घंटे)
• रिपोस्ट: {'✅ चालू' if repost_enabled else '❌ बंद'}
• एक्टिव पोस्ट: {len(get_all_active_posts())}
"""
    
    await context.bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=reply_markup)

# ===== कमांड हैंडलर =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start कमांड"""
    await update.message.reply_text("🚀 बॉट शुरू हो गया! सारी सेटिंग्स डेटाबेस में सेव होंगी। कृपया नीचे दिए मेनू का उपयोग करें।")
    await main_menu(update, context)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/menu कमांड - मेनू दिखाएं"""
    await main_menu(update, context)

# ===== कॉलबैक हैंडलर =====
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "set_channel":
        context.user_data["awaiting_channel"] = True
        await query.edit_message_text(
            "📢 *चैनल सेट करें*\n\n"
            "कृपया अपने चैनल का यूजरनेम या आईडी भेजें।\n\n"
            "उदाहरण: @my_channel या -1001234567890\n\n"
            "⚠️ बॉट को चैनल में एडमिन बनाना न भूलें!\n\n"
            "💾 यह सेटिंग डेटाबेस में सेव हो जाएगी।",
            parse_mode='Markdown'
        )
        
    elif data == "set_time":
        delete_time = get_setting("delete_after_seconds")
        keyboard = [
            [InlineKeyboardButton("1 घंटा (3600 सेकंड)", callback_data="time_3600")],
            [InlineKeyboardButton("6 घंटे (21600 सेकंड)", callback_data="time_21600")],
            [InlineKeyboardButton("12 घंटे (43200 सेकंड)", callback_data="time_43200")],
            [InlineKeyboardButton("24 घंटे (86400 सेकंड)", callback_data="time_86400")],
            [InlineKeyboardButton("2 दिन (172800 सेकंड)", callback_data="time_172800")],
            [InlineKeyboardButton("7 दिन (604800 सेकंड)", callback_data="time_604800")],
            [InlineKeyboardButton("30 दिन (2592000 सेकंड)", callback_data="time_2592000")],
            [InlineKeyboardButton("🎯 कस्टम समय", callback_data="time_custom")],
            [InlineKeyboardButton("◀️ वापस", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"⏰ *डिलीट और रिपोस्ट का समय चुनें*\n\n"
            f"मौजूदा समय: {delete_time} सेकंड ({round(delete_time/3600, 1)} घंटे)\n\n"
            f"💾 यह सेटिंग डेटाबेस में सेव हो जाएगी।",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data.startswith("time_"):
        time_value = data.split("_")[1]
        if time_value == "custom":
            context.user_data["awaiting_custom_time"] = True
            await query.edit_message_text(
                "🎯 *कस्टम समय*\n\n"
                "कृपया सेकंड में समय भेजें।\n"
                "उदाहरण: 3600 (1 घंटा), 86400 (24 घंटे)\n\n"
                "📝 सिर्फ नंबर भेजें (सेकंड में):\n\n"
                "💾 यह सेटिंग डेटाबेस में सेव हो जाएगी।",
                parse_mode='Markdown'
            )
        else:
            seconds = int(time_value)
            set_setting("delete_after_seconds", seconds)
            await query.edit_message_text(
                f"✅ समय अपडेट हो गया और डेटाबेस में सेव हो गया!\n\n"
                f"नया समय: {seconds} सेकंड ({round(seconds/3600, 1)} घंटे)\n\n"
                f"अब नई पोस्ट {seconds} सेकंड बाद डिलीट और रिपोस्ट होगी।"
            )
            await asyncio.sleep(2)
            await main_menu(update, context, query.message.chat.id)
    
    elif data == "toggle_repost":
        current = get_setting("repost_enabled")
        new_value = not current
        set_setting("repost_enabled", new_value)
        status_text = "चालू ✅" if new_value else "बंद ❌"
        await query.edit_message_text(
            f"🔄 रिपोस्ट फीचर {status_text} कर दिया गया!\n\n"
            f"अब रिपोस्ट: {status_text}\n\n"
            f"💾 यह सेटिंग डेटाबेस में सेव हो गई है।"
        )
        await asyncio.sleep(2)
        await main_menu(update, context, query.message.chat.id)
    
    elif data == "status":
        source_channel = get_setting("source_channel")
        delete_time = get_setting("delete_after_seconds")
        repost_enabled = get_setting("repost_enabled")
        active_posts = get_all_active_posts()
        
        status_text = f"""
📊 *बॉट स्टेटस (डेटाबेस से)*

📢 *सोर्स चैनल:* {source_channel if source_channel else '❌ सेट नहीं'}
⏰ *डिलीट/रिपोस्ट समय:* {delete_time} सेकंड ({round(delete_time/3600, 1)} घंटे)
🔄 *रिपोस्ट स्टेटस:* {'✅ चालू' if repost_enabled else '❌ बंद'}
📝 *एक्टिव पोस्ट:* {len(active_posts)}

🤖 *बॉट स्टेटस:* ऑनलाइन
💾 *डेटाबेस:* SQLite (परमानेंट)
        """
        
        # पोस्ट की लिस्ट दिखाएं
        if active_posts:
            status_text += "\n\n📋 *एक्टिव पोस्ट:*\n"
            for i, post in enumerate(active_posts[:5], 1):
                delete_time_str = post["delete_at"].strftime("%Y-%m-%d %H:%M:%S") if post["delete_at"] else "N/A"
                status_text += f"{i}. मैसेज ID: {post['message_id']} (डिलीट: {delete_time_str})\n"
            if len(active_posts) > 5:
                status_text += f"\n... और {len(active_posts) - 5} पोस्ट"
        
        await query.edit_message_text(status_text, parse_mode='Markdown')
        await asyncio.sleep(5)
        await main_menu(update, context, query.message.chat.id)
    
    elif data == "clear_posts":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM posts WHERE status = 'active'")
        conn.commit()
        conn.close()
        await query.edit_message_text("🗑️ सभी एक्टिव पोस्ट डेटाबेस से हटा दिए गए!")
        await asyncio.sleep(2)
        await main_menu(update, context, query.message.chat.id)
    
    elif data == "back":
        await main_menu(update, context, query.message.chat.id)
    
    elif data == "close":
        await query.edit_message_text("❌ मेनू बंद किया गया। फिर से खोलने के लिए /menu टाइप करें।")

# ===== टेक्स्ट मैसेज हैंडलर =====
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
                await update.message.reply_text("❌ चैनल नहीं मिला! कृपया सही यूजरनेम डालें।")
                return
        else:
            try:
                channel_id = int(channel_input)
            except:
                await update.message.reply_text("❌ गलत फॉर्मेट! कृपया @username या नंबर आईडी डालें।")
                return
        
        set_setting("source_channel", channel_id)
        await update.message.reply_text(
            f"✅ चैनल सेट हो गया और डेटाबेस में सेव हो गया!\n\n"
            f"📢 चैनल आईडी: `{channel_id}`\n\n"
            f"⚠️ याद रखें: बॉट को इस चैनल में एडमिन बनाना जरूरी है!",
            parse_mode='Markdown'
        )
        await main_menu(update, context, user_id)
    
    elif context.user_data.get("awaiting_custom_time"):
        context.user_data["awaiting_custom_time"] = False
        try:
            seconds = int(text)
            if seconds <= 0:
                await update.message.reply_text("❌ कृपया 0 से बड़ा नंबर डालें!")
                return
            set_setting("delete_after_seconds", seconds)
            await update.message.reply_text(
                f"✅ समय सेट हो गया और डेटाबेस में सेव हो गया!\n\n"
                f"नया समय: {seconds} सेकंड ({round(seconds/3600, 1)} घंटे)"
            )
        except ValueError:
            await update.message.reply_text("❌ कृपया सिर्फ नंबर भेजें (सेकंड में)!")
        await main_menu(update, context, user_id)
    
    else:
        pass

# ===== चैनल से नई पोस्ट आने पर =====
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    repost_enabled = get_setting("repost_enabled")
    if not repost_enabled:
        return
    
    source_channel = get_setting("source_channel")
    if source_channel is None:
        print("⚠️ कोई चैनल सेट नहीं है!")
        return
    
    chat_id = update.effective_chat.id
    if chat_id != source_channel:
        return
    
    try:
        message = update.channel_post
        message_id = message.message_id
        
        # पिछली पोस्ट डिलीट करें
        last_post = get_last_post()
        if last_post:
            try:
                await bot.bot.delete_message(last_post["chat_id"], last_post["message_id"])
                update_post_status(last_post["message_id"], "deleted")
                print(f"🗑️ पुरानी पोस्ट डिलीट: {last_post['message_id']}")
            except Exception as e:
                print(f"पुरानी पोस्ट डिलीट नहीं हो पाई: {e}")
        
        # नई पोस्ट डेटा सेव करें
        text = message.text or message.caption or ""
        media_type = None
        file_id = None
        
        if message.photo:
            media_type = "photo"
            file_id = message.photo[-1].file_id
        elif message.video:
            media_type = "video"
            file_id = message.video.file_id
        elif message.document:
            media_type = "document"
            file_id = message.document.file_id
        
        save_post(message_id, chat_id, text, media_type, file_id)
        print(f"📥 नई पोस्ट सेव: {message_id}")
        
        # तय समय बाद रिपोस्ट करें
        delete_time = get_setting("delete_after_seconds")
        asyncio.create_task(schedule_repost(message_id, chat_id, text, media_type, file_id, delete_time))
        
    except Exception as e:
        print(f"❌ पोस्ट प्रोसेस एरर: {e}")

# ===== रिपोस्ट शेड्यूल =====
async def schedule_repost(message_id, chat_id, text, media_type, file_id, delay):
    await asyncio.sleep(delay)
    
    repost_enabled = get_setting("repost_enabled")
    if not repost_enabled:
        return
    
    try:
        if media_type == "photo":
            await bot.bot.send_photo(chat_id, file_id, caption=text if text else None)
        elif media_type == "video":
            await bot.bot.send_video(chat_id, file_id, caption=text if text else None)
        elif media_type == "document":
            await bot.bot.send_document(chat_id, file_id, caption=text if text else None)
        else:
            await bot.bot.send_message(chat_id, text)
        
        update_post_status(message_id, "reposted")
        print(f"🔄 पोस्ट रिपोस्ट हो गई: {message_id}")
        
    except Exception as e:
        print(f"❌ रिपोस्ट एरर: {e}")

# ===== वेबहुक सर्वर =====
WEBHOOK_URL = f"{RENDER_URL}/webhook"

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/webhook':
            try:
                length = int(self.headers['Content-Length'])
                data = json.loads(self.rfile.read(length))
                update = Update.de_json(data, bot.bot)
                asyncio.create_task(bot.update_queue.put(update))
                self.send_response(200)
                self.end_headers()
            except Exception as e:
                print(f"❌ वेबहुक एरर: {e}")
                self.send_response(500)
                self.end_headers()
    
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

# ===== मेन =====
async def main():
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("menu", menu))
    bot.add_handler(CallbackQueryHandler(button_callback))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    bot.add_handler(MessageHandler(filters.CHANNEL_POST, handle_channel_post))
    
    await bot.bot.set_webhook(WEBHOOK_URL)
    print(f"✅ वेबहुक सेट: {WEBHOOK_URL}")
    
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    
    async with bot:
        await bot.start()
        print(f"🤖 बॉट चालू है! डेटाबेस: {DB_PATH}")
        
        import threading
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        
        await asyncio.Event().wait()

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 ऑटो-डिलीट और रिपोस्ट बॉट")
    print("💾 डेटाबेस: SQLite (परमानेंट स्टोरेज)")
    print("📱 बॉट में /start करके कंट्रोल करें")
    print("=" * 50)
    asyncio.run(main())
