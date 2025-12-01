#!/usr/bin/env python3
"""
Telegram Bot for "Я Бомж" WebApp
Supports webhook mode (Railway) and long-polling (local development)
Includes battle system with boss fights
"""

import os
import json
import logging
import traceback
import random
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

# Config file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MOVES_CONFIG_PATH = os.path.join(BASE_DIR, "configs", "moves.json")
BOSSES_CONFIG_PATH = os.path.join(BASE_DIR, "configs", "bosses.json")

app = Flask(__name__)
CORS(app)

# Load / save users
users_data = {}

# Battle config cache
moves_config = {}
bosses_config = {}


def load_json_config(path):
    """Load a JSON config file"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to load config from %s", path)
        return {}


def load_battle_configs():
    """Load battle configuration files"""
    global moves_config, bosses_config
    moves_config = load_json_config(MOVES_CONFIG_PATH)
    bosses_config = load_json_config(BOSSES_CONFIG_PATH)
    logger.info("Loaded %d moves and %d bosses", len(moves_config), len(bosses_config))


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
            "last_action": datetime.utcnow().isoformat(),
            "battle": None
        }
        save_users()
    # Ensure battle field exists for legacy users
    if "battle" not in users_data[user_id_str]:
        users_data[user_id_str]["battle"] = None
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


# ==================== BATTLE SYSTEM ====================

def calculate_player_max_hp(user):
    """Calculate player max HP based on strength: base 120 + strength*2"""
    return 120 + user.get("strength", 10) * 2


def calculate_damage(move, user, boss):
    """
    Calculate damage for a move.
    Returns tuple: (damage, is_crit, is_miss, log_message)
    """
    base_damage = move.get("base_damage", 10)
    strength_bonus = user.get("strength", 10)
    weapon_bonus = 0  # Placeholder for future weapon system
    
    # Check for miss
    if random.random() < move.get("miss_chance", 0):
        return (0, False, True, f"Промах! {move.get('name_ru', move.get('name'))} не попал.")
    
    # Calculate base damage with bonuses
    damage = base_damage + strength_bonus + weapon_bonus
    
    # Apply boss defense
    defense = boss.get("defense", 0)
    damage = max(1, damage - defense)
    
    # Check for crit
    is_crit = random.random() < move.get("crit_chance", 0)
    if is_crit:
        damage = int(damage * move.get("crit_multiplier", 1.5))
        log_msg = f"КРИТ! {move.get('name_ru', move.get('name'))} наносит {damage} урона!"
    else:
        log_msg = f"{move.get('name_ru', move.get('name'))} наносит {damage} урона."
    
    return (damage, is_crit, False, log_msg)


def apply_move_effects(move, battle, boss):
    """Apply move effects (bleed, stun) to the battle state"""
    effects = move.get("effects", [])
    log_entries = []
    
    for effect in effects:
        effect_type = effect.get("type")
        
        if effect_type == "bleed":
            # Check boss bleed resistance
            resist = boss.get("resistances", {}).get("bleed", 0)
            if random.random() >= resist:
                turns = effect.get("turns", 3)
                dmg_per_turn = effect.get("damage_per_turn", 5)
                
                # Stack bleed: refresh duration, add damage (cap at 3 stacks)
                current_bleed = battle["effects"].get("bleed") or {"remaining": 0, "dmg_per_turn": 0, "stacks": 0}
                new_stacks = min(3, current_bleed.get("stacks", 0) + 1)
                new_dmg = min(dmg_per_turn * 3, current_bleed.get("dmg_per_turn", 0) + dmg_per_turn)
                
                battle["effects"]["bleed"] = {
                    "remaining": turns,
                    "dmg_per_turn": new_dmg,
                    "stacks": new_stacks
                }
                log_entries.append(f"🩸 Кровотечение наложено! ({new_stacks}x{new_dmg} за ход)")
            else:
                log_entries.append("🛡️ Босс сопротивляется кровотечению!")
        
        elif effect_type == "stun":
            # Check boss stun resistance
            resist = boss.get("resistances", {}).get("stun", 0)
            base_chance = effect.get("chance", 0.3)
            final_chance = base_chance * (1 - resist)
            
            if random.random() < final_chance:
                battle["effects"]["stunned"] = True
                log_entries.append("💫 Босс оглушён! Пропускает атаку.")
            else:
                log_entries.append("🛡️ Босс устоял от оглушения.")
    
    return log_entries


def process_bleed_tick(battle):
    """Process bleed damage at the start of turn"""
    bleed = battle["effects"].get("bleed")
    if bleed and bleed.get("remaining", 0) > 0:
        dmg = bleed["dmg_per_turn"]
        battle["boss_hp"] -= dmg
        bleed["remaining"] -= 1
        
        if bleed["remaining"] <= 0:
            battle["effects"]["bleed"] = None
            return f"🩸 Кровотечение наносит {dmg} урона. Эффект закончился."
        return f"🩸 Кровотечение наносит {dmg} урона. (Осталось {bleed['remaining']} ходов)"
    return None


def process_boss_attack(battle, boss):
    """Process boss counterattack"""
    # Check if stunned
    if battle["effects"].get("stunned"):
        battle["effects"]["stunned"] = False
        return "💫 Босс оглушён и пропускает ход!"
    
    # Calculate boss damage
    damage_range = boss.get("damage_range", [10, 20])
    damage = random.randint(damage_range[0], damage_range[1])
    
    # Check rage mode
    boss_max_hp = boss.get("hp", 100)
    boss_current_hp = battle["boss_hp"]
    rage_threshold = boss.get("rage_threshold", 0.3)
    
    if boss_current_hp / boss_max_hp <= rage_threshold:
        rage_multiplier = boss.get("rage_bonus_damage", 1.5)
        damage = int(damage * rage_multiplier)
        battle["player_hp"] -= damage
        return f"😡 ЯРОСТЬ! {boss.get('name_ru', boss.get('name'))} наносит {damage} урона!"
    
    battle["player_hp"] -= damage
    return f"👊 {boss.get('name_ru', boss.get('name'))} наносит {damage} урона."


def generate_loot(boss, won):
    """Generate loot rewards for battle end"""
    if not won:
        return {"rub": 0, "usd": 0, "exp": 0, "items": []}
    
    loot_config = boss.get("loot", {})
    rewards = {
        "rub": 0,
        "usd": 0,
        "exp": loot_config.get("exp", 0),
        "items": []
    }
    
    # Rubles
    rub_range = loot_config.get("rub", {})
    if rub_range:
        rewards["rub"] = random.randint(rub_range.get("min", 0), rub_range.get("max", 0))
    
    # Dollars (optional)
    usd_range = loot_config.get("usd", {})
    if usd_range:
        rewards["usd"] = random.randint(usd_range.get("min", 0), usd_range.get("max", 0))
    
    # Item drops
    items = loot_config.get("items", [])
    for item in items:
        if random.random() < item.get("chance", 0):
            rewards["items"].append(item.get("id"))
    
    return rewards


# Validate token
if not BOT_TOKEN:
    logger.error("BOT_TOKEN is empty. Set BOT_TOKEN in Railway Variables and redeploy.")
    bot = None
else:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)


# ==================== FLASK ROUTES ====================

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
        user_obj = get_or_create_user(user_id)
        restore_energy(user_obj)
        if action_name == "dig_trash":
            if user_obj["energy"] < 10:
                return jsonify({"error": "Недостаточно энергии"}), 400
            user_obj["energy"] -= 10
            user_obj["money_rub"] += 50
            user_obj["exp"] += 10
        elif action_name == "collect_bottles":
            if user_obj["energy"] < 5:
                return jsonify({"error": "Недостаточно энергии"}), 400
            user_obj["energy"] -= 5
            user_obj["money_usd"] += 0.5
            user_obj["exp"] += 5
        elif action_name == "train_strength":
            if user_obj["energy"] < 15:
                return jsonify({"error": "Недостаточно энергии"}), 400
            user_obj["energy"] -= 15
            user_obj["strength"] += 1
            user_obj["exp"] += 15
        save_users()
        return jsonify({"user": user_obj})
    except Exception:
        logger.exception("Exception in /action")
        return jsonify({"error": "server error"}), 500


# ==================== BATTLE ENDPOINTS ====================

@app.route("/battle/config", methods=["GET"])
def battle_config():
    """Return battle configuration (moves and bosses) for the frontend"""
    try:
        return jsonify({
            "ok": True,
            "moves": moves_config,
            "bosses": bosses_config
        })
    except Exception:
        logger.exception("Exception in /battle/config")
        return jsonify({"ok": False, "error": "server error"}), 500


@app.route("/battle/start", methods=["POST"])
def battle_start():
    """Start a new battle"""
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        boss_id = data.get("boss_id", "street_bully")
        
        if not user_id:
            return jsonify({"ok": False, "error": "Missing user_id"}), 400
        
        user_obj = get_or_create_user(user_id)
        restore_energy(user_obj)
        
        # Check if already in battle
        if user_obj.get("battle") and user_obj["battle"].get("active"):
            return jsonify({"ok": False, "error": "Уже есть активный бой"}), 400
        
        # Check if boss exists
        if boss_id not in bosses_config:
            return jsonify({"ok": False, "error": f"Босс '{boss_id}' не найден"}), 400
        
        boss = bosses_config[boss_id]
        
        # Initialize battle state
        player_max_hp = calculate_player_max_hp(user_obj)
        
        battle_state = {
            "active": True,
            "boss_id": boss_id,
            "player_hp": player_max_hp,
            "player_max_hp": player_max_hp,
            "boss_hp": boss["hp"],
            "boss_max_hp": boss["hp"],
            "effects": {
                "bleed": None,
                "stunned": False
            },
            "turn": 0,
            "log": [f"⚔️ Бой начался! Противник: {boss.get('name_ru', boss.get('name'))}"],
            "finished": False,
            "player_won": False
        }
        
        user_obj["battle"] = battle_state
        save_users()
        
        return jsonify({
            "ok": True,
            "battle": battle_state,
            "user": user_obj
        })
    except Exception:
        logger.exception("Exception in /battle/start")
        return jsonify({"ok": False, "error": "server error"}), 500


@app.route("/battle/turn", methods=["POST"])
def battle_turn():
    """Perform a battle turn"""
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        move_key = data.get("move")
        
        if not user_id:
            return jsonify({"ok": False, "error": "Missing user_id"}), 400
        if not move_key:
            return jsonify({"ok": False, "error": "Missing move"}), 400
        
        user_obj = get_or_create_user(user_id)
        restore_energy(user_obj)
        
        battle = user_obj.get("battle")
        
        # Validate battle state
        if not battle or not battle.get("active"):
            return jsonify({"ok": False, "error": "Нет активного боя"}), 400
        
        if battle.get("finished"):
            return jsonify({
                "ok": True,
                "battle": battle,
                "finished": True,
                "player_won": battle.get("player_won", False)
            })
        
        # Validate move
        if move_key not in moves_config:
            return jsonify({"ok": False, "error": f"Приём '{move_key}' не найден"}), 400
        
        move = moves_config[move_key]
        energy_cost = move.get("energy_cost", 5)
        
        # Check energy
        if user_obj["energy"] < energy_cost:
            return jsonify({"ok": False, "error": "Недостаточно энергии"}), 400
        
        boss_id = battle["boss_id"]
        boss = bosses_config.get(boss_id, {})
        
        # Increment turn
        battle["turn"] += 1
        turn_log = []
        
        # Process bleed damage at start of turn
        bleed_msg = process_bleed_tick(battle)
        if bleed_msg:
            turn_log.append(bleed_msg)
        
        # Check if boss died from bleed
        if battle["boss_hp"] <= 0:
            battle["finished"] = True
            battle["player_won"] = True
            battle["active"] = False
            turn_log.append("🎉 Победа! Босс повержен!")
            battle["log"].extend(turn_log)
            save_users()
            return jsonify({
                "ok": True,
                "battle": battle,
                "finished": True,
                "player_won": True
            })
        
        # Deduct energy
        user_obj["energy"] -= energy_cost
        
        # Calculate and apply damage
        damage, is_crit, is_miss, damage_log = calculate_damage(move, user_obj, boss)
        turn_log.append(damage_log)
        
        if not is_miss:
            battle["boss_hp"] -= damage
            
            # Apply move effects
            effect_logs = apply_move_effects(move, battle, boss)
            turn_log.extend(effect_logs)
        
        # Check if boss defeated
        if battle["boss_hp"] <= 0:
            battle["finished"] = True
            battle["player_won"] = True
            battle["active"] = False
            turn_log.append("🎉 Победа! Босс повержен!")
        else:
            # Boss counterattack
            boss_log = process_boss_attack(battle, boss)
            turn_log.append(boss_log)
            
            # Check if player defeated
            if battle["player_hp"] <= 0:
                battle["finished"] = True
                battle["player_won"] = False
                battle["active"] = False
                turn_log.append("💀 Поражение! Ты проиграл...")
        
        # Update log (keep last 20 entries)
        battle["log"].extend(turn_log)
        battle["log"] = battle["log"][-20:]
        
        save_users()
        
        return jsonify({
            "ok": True,
            "battle": battle,
            "user": user_obj,
            "finished": battle.get("finished", False),
            "player_won": battle.get("player_won", False)
        })
    except Exception:
        logger.exception("Exception in /battle/turn")
        return jsonify({"ok": False, "error": "server error"}), 500


@app.route("/battle/end", methods=["POST"])
def battle_end():
    """End the battle and claim rewards"""
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        
        if not user_id:
            return jsonify({"ok": False, "error": "Missing user_id"}), 400
        
        user_obj = get_or_create_user(user_id)
        battle = user_obj.get("battle")
        
        if not battle:
            return jsonify({"ok": False, "error": "Нет боя для завершения"}), 400
        
        if not battle.get("finished"):
            return jsonify({"ok": False, "error": "Бой ещё не завершён"}), 400
        
        # Generate rewards
        boss_id = battle.get("boss_id", "street_bully")
        boss = bosses_config.get(boss_id, {})
        rewards = generate_loot(boss, battle.get("player_won", False))
        
        # Apply rewards
        if battle.get("player_won"):
            user_obj["money_rub"] += rewards["rub"]
            user_obj["money_usd"] += rewards["usd"]
            user_obj["exp"] += rewards["exp"]
        
        # Clear battle state
        user_obj["battle"] = None
        save_users()
        
        return jsonify({
            "ok": True,
            "rewards": rewards,
            "user": user_obj,
            "player_won": battle.get("player_won", False)
        })
    except Exception:
        logger.exception("Exception in /battle/end")
        return jsonify({"ok": False, "error": "server error"}), 500


# Bot handlers
if bot is not None:
    @bot.message_handler(commands=["start"])
    def start(message):
        try:
            user_id = message.from_user.id
            user_obj = get_or_create_user(user_id)
            restore_energy(user_obj)
            markup = types.InlineKeyboardMarkup()
            if WEBHOOK_URL:
                web_app = types.WebAppInfo(url=f"{WEBHOOK_URL}/webapp?user_id={user_id}")
                markup.add(types.InlineKeyboardButton("🎮 Открыть игру (WebApp)", web_app=web_app))
            markup.add(types.InlineKeyboardButton("📊 Профиль", callback_data="show_stats"))
            bot.send_message(
                user_id,
                f"🎮 Добро пожаловать в Bomzh Clicker!\n\n"
                f"Уровень: {user_obj['level']}\n"
                f"Рубли: {user_obj['money_rub']} ₽\n"
                f"Доллары: ${user_obj['money_usd']}\n\n"
                f"Нажми кнопку ниже.",
                reply_markup=markup
            )
        except Exception:
            logger.exception("Error in start handler")

    @bot.message_handler(commands=["stats", "status"])
    def stats(message):
        try:
            user_id = message.from_user.id
            user_obj = get_or_create_user(user_id)
            restore_energy(user_obj)
            stats_text = (
                f"📊 Профиль:\n\n"
                f"Уровень: {user_obj['level']}\n"
                f"Опыт: {user_obj['exp']}\n"
                f"Рубли: {user_obj['money_rub']} ₽\n"
                f"Доллары: ${user_obj['money_usd']}\n"
                f"Энергия: {user_obj['energy']}/{user_obj['max_energy']}\n"
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
    load_battle_configs()
    logger.info("Flask app is ready. Routes: /, /health, /webhook, /action, /battle/*")
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
            app.run(host="0.0.0.0", port=PORT)
