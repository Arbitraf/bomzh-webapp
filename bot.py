#!/usr/bin/env python3
"""
Telegram Bot for "Я Бомж" WebApp
Supports webhook mode (Railway) and long-polling (local development)
"""

import os
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

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# In-memory user storage (for demo purposes - use a database in production)
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
            if user['exp'] >= user['level'] * 100:
                user['level'] += 1
                user['max_energy'] += 10
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

# Telegram webhook endpoint
@app.route(f'/webhook/{BOT_TOKEN}', methods=['POST'])
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
        webhook_url = f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")

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
