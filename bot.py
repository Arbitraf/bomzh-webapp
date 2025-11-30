copilot/add-telegram-bot-files
#!/usr/bin/env python3
"""
Telegram Bot for "Я Бомж" WebApp
Supports webhook mode (Railway) and long-polling (local development)
"""

import os
import hashlib
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import telebot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')
USE_POLLING = os.environ.get('USE_POLLING', 'false').lower() == 'true'
PORT = int(os.environ.get('PORT', 5000))
WEBAPP_URL = os.environ.get('WEBAPP_URL', '')

# Validate required environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# Generate a secure webhook secret from the bot token (avoid exposing token in URL)
WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]

# Game configuration constants
LEVEL_UP_EXP_MULTIPLIER = 100  # exp needed = level * this value
LEVEL_UP_ENERGY_BONUS = 10     # bonus max_energy per level

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# In-memory user storage
# WARNING: Data is lost on server restart/redeploy. Use a database (PostgreSQL, Redis, etc.) for production.
users_db = {}

def get_or_create_user(user_id):
    """Get or create a user in the database"""
    if user_id not in users_db:
        users_db[user_id] = {
            'user_id': user_id,
            'level': 1,
            'exp': 0,
            'money_rub': 100,
            'money_usd': 0,
            'energy': 100,
            'max_energy': 100,
            'strength': 1,
            'pity': 10,
            'coolness': 0
        }
    return users_db[user_id]

def perform_action(user, action):
    """Perform a game action for the user"""
    if action == 'dig_trash':
        if user['energy'] >= 10:
            user['energy'] -= 10
            user['exp'] += 5
            user['money_rub'] += 10
            user['pity'] += 1
            # Level up check
            if user['exp'] >= user['level'] * LEVEL_UP_EXP_MULTIPLIER:
                user['level'] += 1
                user['max_energy'] += LEVEL_UP_ENERGY_BONUS
            return True
        return False
    elif action == 'collect_bottles':
        if user['energy'] >= 5:
            user['energy'] -= 5
            user['exp'] += 2
            user['money_rub'] += 5
            return True
        return False
    return False

# Flask API endpoints

@app.route('/')
def index():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'Я Бомж Bot is running'})

@app.route('/action', methods=['POST'])
def handle_action():
    """Handle game actions from WebApp"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        user_id = data.get('user_id')
        action = data.get('action')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        if not action:
            return jsonify({'error': 'action is required'}), 400
        
        user = get_or_create_user(user_id)
        success = perform_action(user, action)
        
        if not success:
            return jsonify({'error': 'Not enough energy or invalid action'}), 400
        
        return jsonify({'user': user})
    except Exception as e:
        logger.error(f"Error handling action: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user data"""
    user = get_or_create_user(user_id)
    return jsonify({'user': user})

# Telegram webhook endpoint (uses hashed secret instead of raw token for security)
@app.route(f'/webhook/{WEBHOOK_SECRET}', methods=['POST'])
def webhook():
    """Handle Telegram webhook updates"""
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return '', 200
        return '', 403
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return '', 500

# Telegram bot handlers

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Handle /start command"""
    user_id = message.from_user.id
    user = get_or_create_user(user_id)
    
    markup = telebot.types.InlineKeyboardMarkup()
    if WEBAPP_URL:
        webapp_btn = telebot.types.InlineKeyboardButton(
            text="🎮 Играть",
            web_app=telebot.types.WebAppInfo(url=WEBAPP_URL)
        )
        markup.add(webapp_btn)
    
    welcome_text = (
        f"👋 Привет, бомж!\n\n"
        f"📊 Твой уровень: {user['level']}\n"
        f"💵 Рубли: {user['money_rub']}\n"
        f"⚡ Энергия: {user['energy']}/{user['max_energy']}\n\n"
        "Нажми кнопку ниже, чтобы начать играть!"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    """Handle /stats command"""
    user_id = message.from_user.id
    user = get_or_create_user(user_id)
    
    stats_text = (
        f"📊 Статистика бомжа:\n\n"
        f"👤 ID: {user['user_id']}\n"
        f"⭐ Уровень: {user['level']}\n"
        f"✨ Опыт: {user['exp']}\n"
        f"💵 Рубли: {user['money_rub']}\n"
        f"💲 Доллары: {user['money_usd']}\n"
        f"⚡ Энергия: {user['energy']}/{user['max_energy']}\n"
        f"💪 Сила: {user['strength']}\n"
        f"😔 Жалкость: {user['pity']}\n"
        f"😎 Крутость: {user['coolness']}"
    )
    
    bot.send_message(message.chat.id, stats_text)

@bot.message_handler(commands=['help'])
def handle_help(message):
    """Handle /help command"""
    help_text = (
        "🆘 Помощь по игре 'Я Бомж':\n\n"
        "/start - Начать игру\n"
        "/stats - Показать статистику\n"
        "/help - Показать эту справку\n\n"
        "🎮 Используй WebApp для:\n"
        "- Копать мусор\n"
        "- Собирать бутылки\n"
        "- Просить милостыню\n"
        "- И многое другое!"
    )
    
    bot.send_message(message.chat.id, help_text)

def setup_webhook():
    """Setup webhook for production"""
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook configured successfully")

def run_polling():
    """Run bot in long-polling mode for local development"""
    logger.info("Starting bot in polling mode...")
    bot.remove_webhook()
    bot.infinity_polling()

if __name__ == '__main__':
    if USE_POLLING:
        # Local development mode
        run_polling()
    else:
        # Production mode with webhook
        setup_webhook()
        app.run(host='0.0.0.0', port=PORT)
import os
import json
import logging
import traceback
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import telebot
from telebot import types
from datetime import datetime

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bomzh-bot")

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")
USE_POLLING = os.getenv("USE_POLLING", "false").lower() == "true"
PORT = int(os.getenv("PORT", 5000))
# Default data file path moved to /tmp for Railway safety
DATA_FILE = os.getenv("DATA_FILE")
if not DATA_FILE or not DATA_FILE.strip():
    DATA_FILE = "/tmp/bomzh_users.json"

app = Flask(__name__)
CORS(app)

# Load / save users
users_data = {}

# Ensure data file exists and is writable
def ensure_data_file():
    try:
        dirname = os.path.dirname(DATA_FILE) or "/tmp"
        if not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)
        return True
    except Exception:
        logger.exception("Failed ensuring data file at %s", DATA_FILE)
        return False

ensure_data_file()

def load_users():
    global users_data
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                users_data = json.load(f) or {}
        else:
            users_data = {}
    except Exception:
        logger.exception("Failed loading users file, starting with empty store.")
        users_data = {}

def save_users():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("Failed saving users file.")


def get_or_create_user(user_id):
    user_id_str = str(user_id)
    if user_id_str not in users_data:
        users_data[user_id_str] = {
            "user_id": user_id,
            "level": 1,
            "exp": 0,
            "money_rub": 0,
            "money_usd": 0,
            "energy": 100,
            "max_energy": 100,
            "strength": 10,
            "pity": 5,
            "coolness": 3,
            "last_action": datetime.utcnow().isoformat()
        }
        save_users()
    return users_data[user_id_str]

def restore_energy(user):
    try:
        last_action = datetime.fromisoformat(user.get("last_action", datetime.utcnow().isoformat()))
    except Exception:
        last_action = datetime.utcnow()
    now = datetime.utcnow()
    minutes = (now - last_action).total_seconds() / 60.0
    energy_restore = int(minutes / 2)
    if energy_restore > 0:
        user["energy"] = min(user["max_energy"], user.get("energy", 0) + energy_restore)
        user["last_action"] = now.isoformat()
        save_users()

# Validate token
if not BOT_TOKEN:
    logger.error("BOT_TOKEN is empty. Set BOT_TOKEN in Railway Variables and redeploy.")
    bot = None
else:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# Health and root endpoints
@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "mode": "polling" if USE_POLLING else "webhook"})

# WebApp route - serves the game UI
@app.route("/webapp", methods=["GET"])
def webapp():
    return render_template("webapp.html")

# User data endpoint
@app.route("/user", methods=["GET"])
def user():
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400
        user_data = get_or_create_user(user_id)
        restore_energy(user_data)
        return jsonify({"user": user_data})
    except Exception:
        logger.exception("Exception in /user")
        return jsonify({"error": "server error"}), 500

# Webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    if bot is None:
        return jsonify({"error": "bot not configured"}), 500
    try:
        json_data = request.get_json(force=True, silent=True)
        if json_data is None:
            # fallback: raw data
            json_data = json.loads(request.data.decode("utf-8"))
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return jsonify({"status": "ok"})
    except Exception:
        logger.exception("Exception in webhook")
        return jsonify({"status": "error", "trace": traceback.format_exc()}), 500

# Game API
@app.route("/action", methods=["POST"])
def action():
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        action_name = data.get("action")
        if not user_id or not action_name:
            return jsonify({"error": "Missing user_id or action"}), 400
        user = get_or_create_user(user_id)
        restore_energy(user)
        if action_name == "dig_trash":
            if user["energy"] < 10:
                return jsonify({"error": "Недостаточно энергии"}), 400
            user["energy"] -= 10
            user["money_rub"] += 50
            user["exp"] += 10
        elif action_name == "collect_bottles":
            if user["energy"] < 5:
                return jsonify({"error": "Недостаточно энергии"}), 400
            user["energy"] -= 5
            user["money_usd"] += 0.5
            user["exp"] += 5
        elif action_name == "train_strength":
            if user["energy"] < 15:
                return jsonify({"error": "Недостаточно энергии"}), 400
            user["energy"] -= 15
            user["strength"] += 1
            user["exp"] += 15
        save_users()
        return jsonify({"user": user})
    except Exception:
        logger.exception("Exception in /action")
        return jsonify({"error": "server error"}), 500

# Bot handlers
if bot is not None:
    @bot.message_handler(commands=["start"])
    def start(message):
        try:
            user_id = message.from_user.id
            user = get_or_create_user(user_id)
            restore_energy(user)
            markup = types.InlineKeyboardMarkup()
            if WEBHOOK_URL:
                web_app = types.WebAppInfo(url=f"{WEBHOOK_URL}/webapp?user_id={user_id}")
                markup.add(types.InlineKeyboardButton("🎮 Открыть игру (WebApp)", web_app=web_app))
            markup.add(types.InlineKeyboardButton("📊 Профиль", callback_data="show_stats"))
            bot.send_message(
                user_id,
                f"🎮 Добро пожаловать в Bomzh Clicker!\n\n"
                f"Уровень: {user['level']}\n"
                f"Рубли: {user['money_rub']} ₽\n"
                f"Доллары: ${user['money_usd']}\n\n"
                f"Нажми кнопку ниже.",
                reply_markup=markup
            )
        except Exception:
            logger.exception("Error in start handler")

    @bot.message_handler(commands=["stats", "status"])
    def stats(message):
        try:
            user_id = message.from_user.id
            user = get_or_create_user(user_id)
            restore_energy(user)
            stats_text = (
                f"📊 Профиль:\n\n"
                f"Уровень: {user['level']}\n"
                f"Опыт: {user['exp']}\n"
                f"Рубли: {user['money_rub']} ₽\n"
                f"Доллары: ${user['money_usd']}\n"
                f"Энергия: {user['energy']}/{user['max_energy']}\n"
            )
            bot.send_message(user_id, stats_text)
        except Exception:
            logger.exception("Error in stats handler")

    @bot.message_handler(func=lambda m: True)
    def fallback(message):
        try:
            bot.reply_to(message, "Используй /start или /stats")
        except Exception:
            logger.exception("Error in fallback handler")


def setup_webhook():
    if bot is None:
        return
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL is not set; skipping webhook setup.")
        return
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info("Webhook set to %s", webhook_url)
    except Exception:
        logger.exception("Failed setting webhook")

if __name__ == "__main__":
    load_users()
    logger.info("Flask app is ready. Routes: /, /health, /webhook, /action")
    if bot is None:
        logger.error("Bot is not configured (BOT_TOKEN missing). Exiting main process.")
    else:
        if USE_POLLING:
            logger.info("Starting bot with polling")
            try:
                bot.infinity_polling(timeout=60, long_polling_timeout=60)
            except Exception:
                logger.exception("Polling stopped due to exception")
        else:
            logger.info("Starting webhook mode (production)")
            setup_webhook()
            app.run(host="0.0.0.0", port=PORT, debug=False)
main
