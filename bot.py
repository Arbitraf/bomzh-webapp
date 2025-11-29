import os
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import telebot
from telebot import types
from datetime import datetime, timedelta

# Инициализация логирования
logging.basicConfig(level=logging. INFO)
logger = logging.getLogger(__name__)

# Получаем переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "7123456789:ABCDefGHIJKlmnoPQRSTuvWXYZaBcDefGH")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://bomzh-webapp-production.up.railway.app")
USE_POLLING = os.getenv("USE_POLLING", "false").lower() == "true"
PORT = int(os.getenv("PORT", 5000))
DATA_FILE = os.getenv("DATA_FILE", "bomzh_users.json")

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

# Хранилище данных пользователей
users_data = {}

def load_users():
    """Загрузить данные пользователей из файла"""
    global users_data
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                users_data = json.load(f)
        else:
            users_data = {}
    except Exception as e:
        logger.error(f"Ошибка при загрузке пользователей: {e}")
        users_data = {}

def save_users():
    """Сохранить данные пользователей в файл"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка при сохранении пользователей: {e}")

def get_or_create_user(user_id):
    """Получить или создать пользователя"""
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
            "last_action": datetime.now().isoformat()
        }
        save_users()
    return users_data[user_id_str]

def restore_energy(user):
    """Восстанавливать энергию со временем"""
    last_action = datetime.fromisoformat(user. get("last_action", datetime.now().isoformat()))
    now = datetime.now()
    time_diff = (now - last_action).total_seconds() / 60  # в минутах
    
    # Восстанавливаем 1 энергию каждые 2 минуты
    energy_restore = int(time_diff / 2)
    if energy_restore > 0:
        user["energy"] = min(user["max_energy"], user["energy"] + energy_restore)
        user["last_action"] = now.isoformat()
        save_users()

@app.route("/webhook", methods=["POST"])
def webhook():
    """Webhook для получения сообщений от Telegram"""
    try:
        json_data = request.get_json()
        update = telebot.types.Update. de_json(json_data)
        bot.process_new_updates([update])
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка в webhook: {e}")
        return jsonify({"status": "error"}), 500

@app.route("/action", methods=["POST"])
def action():
    """API endpoint для действий из WebApp"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        action = data.get("action")
        
        if not user_id or not action:
            return jsonify({"error": "Missing user_id or action"}), 400
        
        user = get_or_create_user(user_id)
        restore_energy(user)
        
        # Обработка действий
        if action == "dig_trash":
            if user["energy"] < 10:
                return jsonify({"error": "Недостаточно энергии"}), 400
            
            user["energy"] -= 10
            user["money_rub"] += 50
            user["exp"] += 10
            
            # Прогресс уровня
            if user["exp"] >= user["level"] * 100:
                user["level"] += 1
                user["max_energy"] += 20
                user["energy"] = user["max_energy"]
            
        elif action == "collect_bottles":
            if user["energy"] < 5:
                return jsonify({"error": "Недостаточно энергии"}), 400
            
            user["energy"] -= 5
            user["money_usd"] += 0.5
            user["exp"] += 5
        
        elif action == "train_strength":
            if user["energy"] < 15:
                return jsonify({"error": "Недостаточно энергии"}), 400
            
            user["energy"] -= 15
            user["strength"] += 1
            user["exp"] += 15
        
        save_users()
        return jsonify({"user": user})
    
    except Exception as e:
        logger.error(f"Ошибка в /action: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/user/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Получить информацию о пользователе"""
    try:
        user = get_or_create_user(user_id)
        restore_energy(user)
        return jsonify({"user": user})
    except Exception as e:
        logger.error(f"Ошибка в /user: {e}")
        return jsonify({"error": str(e)}), 500

@bot.message_handler(commands=["start"])
def start(message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    user = get_or_create_user(user_id)
    
    # Создаем inline клавиатуру с WebApp кнопкой
    markup = types.InlineKeyboardMarkup()
    web_app = types.WebAppInfo(url=f"{WEBHOOK_URL}?user_id={user_id}")
    markup.add(types.InlineKeyboardButton("🎮 Открыть игру (WebApp)", web_app=web_app))
    
    bot.send_message(
        user_id,
        f"🎮 Добро пожаловать в Bomzh Clicker!\n\n"
        f"Твой уровень: {user['level']}\n"
        f"Твои рубли: {user['money_rub']} ₽\n"
        f"Твои доллары: ${user['money_usd']}\n\n"
        f"Нажми на кнопку ниже, чтобы открыть игру! ",
        reply_markup=markup
    )

@bot.message_handler(commands=["stats"])
def stats(message):
    """Команда для просмотра статистики"""
    user_id = message.from_user.id
    user = get_or_create_user(user_id)
    restore_energy(user)
    
    stats_text = (
        f"📊 Твоя статистика:\n\n"
        f"Уровень: {user['level']}\n"
        f"Опыт: {user['exp']}\n"
        f"Рубли: {user['money_rub']} ₽\n"
        f"Доллары: ${user['money_usd']}\n"
        f"Энергия: {user['energy']}/{user['max_energy']}\n"
        f"Сила: {user['strength']}\n"
        f"Жалкость: {user['pity']}\n"
        f"Крутость: {user['coolness']}"
    )
    bot.send_message(user_id, stats_text)

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """Эхо для остальных сообщений"""
    bot.reply_to(message, "Используй команду /start или /stats")

def setup_webhook():
    """Установить webhook для бота"""
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook установлен на {webhook_url}")
    except Exception as e:
        logger. error(f"Ошибка при установке webhook: {e}")

@app.route("/", methods=["GET"])
def home():
    """Главная страница"""
    return jsonify({"status": "Bot is running", "mode": "webhook" if not USE_POLLING else "polling"})

if __name__ == "__main__":
    load_users()
    
    if USE_POLLING:
        logger.info("Режим: long-polling")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    else:
        logger.info("Режим: webhook (production)")
        setup_webhook()
        app.run(host="0.0.0.0", port=PORT, debug=False)
