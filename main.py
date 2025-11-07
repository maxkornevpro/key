import os
import json
import threading
import time
import re
import requests
import telebot
from telebot import types
from datetime import datetime, timedelta

# === Конфигурация ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8389528038:AAHaL5tqopydQEUtq6jWX5iVMJmLW5lM9EQ")
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "6053593587,1246190987").split(",")))

# Файл для хранения ключей
KEYS_FILE = os.getenv("KEYS_FILE", "keys.json")

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN)

# === Загрузка и сохранение ключей ===
def load_keys():
    """Загружает ключи из файла"""
    try:
        if os.path.exists(KEYS_FILE):
            with open(KEYS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки ключей: {e}")
    return {}

def save_keys(keys):
    """Сохраняет ключи в файл"""
    try:
        with open(KEYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(keys, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения ключей: {e}")
        return False

# === Вспомогательные функции ===
def parse_duration(duration_str: str):
    """Парсит строку времени (1m, 1h, 1d, 1w, 1year) в секунды"""
    match = re.fullmatch(r"(\d+)([smhdw]|year)", duration_str.strip().lower())
    if not match:
        return None
    value, unit = match.groups()
    value = int(value)
    multipliers = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800,
        'year': 31536000
    }
    return value * multipliers.get(unit, 0)

def format_duration(seconds):
    """Форматирует секунды в читаемый формат"""
    if seconds >= 31536000:
        return f"{seconds // 31536000}year"
    elif seconds >= 604800:
        return f"{seconds // 604800}w"
    elif seconds >= 86400:
        return f"{seconds // 86400}d"
    elif seconds >= 3600:
        return f"{seconds // 3600}h"
    elif seconds >= 60:
        return f"{seconds // 60}m"
    else:
        return f"{seconds}s"

def is_key_valid(key_data):
    """Проверяет, не истек ли ключ"""
    if 'expires_at' not in key_data:
        return True  # Бессрочный ключ
    expires_at = datetime.fromisoformat(key_data['expires_at'])
    return datetime.now() < expires_at

def generate_key():
    """Генерирует уникальный ключ"""
    import uuid
    return str(uuid.uuid4()).replace('-', '')[:16]

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

# === Команды бота ===
@bot.message_handler(commands=['start', 'help'])
def welcome(message):
    """Приветственное сообщение"""
    user_id = message.from_user.id
    
    if is_admin(user_id):
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔑 Получить ключ", "📋 Мои ключи")
        kb.add("👑 Админ панель")
        bot.send_message(
            message.chat.id,
            "👋 Добро пожаловать в бот для получения ключей!\n\n"
            "Используйте кнопки ниже для управления ключами.",
            reply_markup=kb
        )
    else:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("🔑 Получить ключ", "📋 Мои ключи")
        bot.send_message(
            message.chat.id,
            "👋 Добро пожаловать в бот для получения ключей!\n\n"
            "Нажмите 'Получить ключ' чтобы получить новый ключ доступа.",
            reply_markup=kb
        )

@bot.message_handler(func=lambda m: m.text == "🔑 Получить ключ")
def get_key(message):
    """Выдача ключа пользователю"""
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
    keys = load_keys()
    
    # Проверяем, есть ли у пользователя активный ключ
    user_keys = {k: v for k, v in keys.items() if v.get('user_id') == user_id and is_key_valid(v)}
    
    if user_keys:
        active_key = list(user_keys.keys())[0]
        bot.send_message(
            message.chat.id,
            f"✅ У вас уже есть активный ключ:\n\n"
            f"🔑 <code>{active_key}</code>\n\n"
            f"Используйте его для входа в клиент.",
            parse_mode="HTML"
        )
        return
    
    # Генерируем новый ключ
    new_key = generate_key()
    expires_at = datetime.now() + timedelta(days=30)  # По умолчанию 30 дней
    
    keys[new_key] = {
        'user_id': user_id,
        'username': username,
        'created_at': datetime.now().isoformat(),
        'expires_at': expires_at.isoformat(),
        'duration': '30d',
        'active': True
    }
    
    if save_keys(keys):
        bot.send_message(
            message.chat.id,
            f"✅ Ключ успешно создан!\n\n"
            f"🔑 <code>{new_key}</code>\n\n"
            f"⏰ Действителен до: {expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Используйте этот ключ для входа в клиент.",
            parse_mode="HTML"
        )
    else:
        bot.send_message(message.chat.id, "❌ Ошибка при создании ключа. Попробуйте позже.")

@bot.message_handler(func=lambda m: m.text == "📋 Мои ключи")
def my_keys(message):
    """Показывает ключи пользователя"""
    user_id = message.from_user.id
    keys = load_keys()
    
    user_keys = {k: v for k, v in keys.items() if v.get('user_id') == user_id}
    
    if not user_keys:
        bot.send_message(message.chat.id, "❌ У вас нет ключей. Получите новый ключ!")
        return
    
    response = "📋 <b>Ваши ключи:</b>\n\n"
    for key, data in user_keys.items():
        expires_at = datetime.fromisoformat(data.get('expires_at', datetime.now().isoformat()))
        is_valid = is_key_valid(data)
        status = "✅ Активен" if is_valid else "❌ Истек"
        
        response += (
            f"🔑 <code>{key}</code>\n"
            f"📅 Создан: {datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())).strftime('%d.%m.%Y')}\n"
            f"⏰ Истекает: {expires_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📊 Статус: {status}\n\n"
        )
    
    bot.send_message(message.chat.id, response, parse_mode="HTML")

# === Админ команды ===
@bot.message_handler(func=lambda m: m.text == "👑 Админ панель")
def admin_panel(message):
    """Админ панель"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к админ панели.")
        return
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 Все ключи", "➕ Создать ключ", "🗑 Удалить ключ")
    kb.add("👥 Пользователи", "🔙 Назад")
    bot.send_message(message.chat.id, "👑 Админ панель", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📊 Все ключи")
def all_keys(message):
    """Показывает все ключи (только для админов)"""
    if not is_admin(message.from_user.id):
        return
    
    keys = load_keys()
    if not keys:
        bot.send_message(message.chat.id, "❌ Нет ключей")
        return
    
    response = "📊 <b>Все ключи:</b>\n\n"
    for key, data in list(keys.items())[:20]:  # Показываем первые 20
        user_id = data.get('user_id', 'N/A')
        username = data.get('username', 'N/A')
        expires_at = datetime.fromisoformat(data.get('expires_at', datetime.now().isoformat()))
        is_valid = is_key_valid(data)
        status = "✅" if is_valid else "❌"
        
        response += (
            f"{status} <code>{key}</code>\n"
            f"👤 {username} (ID: {user_id})\n"
            f"⏰ {expires_at.strftime('%d.%m.%Y')}\n\n"
        )
    
    if len(keys) > 20:
        response += f"\n... и еще {len(keys) - 20} ключей"
    
    bot.send_message(message.chat.id, response, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "➕ Создать ключ")
def create_key_admin(message):
    """Создание ключа админом"""
    if not is_admin(message.from_user.id):
        return
    
    msg = bot.send_message(
        message.chat.id,
        "Введите данные в формате:\n"
        "<code>user_id:duration</code>\n\n"
        "Примеры:\n"
        "<code>123456789:30d</code>\n"
        "<code>123456789:1year</code>\n\n"
        "Длительность: 1m, 1h, 1d, 1w, 1year",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_create_key)

def process_create_key(message):
    """Обработка создания ключа"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        parts = message.text.split(':')
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Неверный формат. Используйте: user_id:duration")
            return
        
        user_id = int(parts[0].strip())
        duration_str = parts[1].strip()
        
        duration_sec = parse_duration(duration_str)
        if duration_sec is None:
            bot.send_message(message.chat.id, "❌ Неверный формат времени. Пример: 30d, 1year")
            return
        
        keys = load_keys()
        new_key = generate_key()
        expires_at = datetime.now() + timedelta(seconds=duration_sec)
        
        keys[new_key] = {
            'user_id': user_id,
            'username': f'admin_created_{user_id}',
            'created_at': datetime.now().isoformat(),
            'expires_at': expires_at.isoformat(),
            'duration': duration_str,
            'active': True,
            'created_by_admin': True
        }
        
        if save_keys(keys):
            bot.send_message(
                message.chat.id,
                f"✅ Ключ создан!\n\n"
                f"🔑 <code>{new_key}</code>\n"
                f"👤 User ID: {user_id}\n"
                f"⏰ Действителен до: {expires_at.strftime('%d.%m.%Y %H:%M')}",
                parse_mode="HTML"
            )
        else:
            bot.send_message(message.chat.id, "❌ Ошибка при сохранении")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: m.text == "🗑 Удалить ключ")
def delete_key_prompt(message):
    """Запрос на удаление ключа"""
    if not is_admin(message.from_user.id):
        return
    
    msg = bot.send_message(
        message.chat.id,
        "Введите ключ для удаления:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_delete_key)

def process_delete_key(message):
    """Обработка удаления ключа"""
    if not is_admin(message.from_user.id):
        return
    
    key = message.text.strip()
    keys = load_keys()
    
    if key not in keys:
        bot.send_message(message.chat.id, "❌ Ключ не найден")
        return
    
    del keys[key]
    if save_keys(keys):
        bot.send_message(message.chat.id, f"✅ Ключ <code>{key}</code> удален", parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "❌ Ошибка при удалении")

@bot.message_handler(func=lambda m: m.text == "👥 Пользователи")
def show_users(message):
    """Показывает статистику пользователей"""
    if not is_admin(message.from_user.id):
        return
    
    keys = load_keys()
    users = {}
    
    for key, data in keys.items():
        user_id = data.get('user_id')
        if user_id:
            if user_id not in users:
                users[user_id] = {
                    'username': data.get('username', 'N/A'),
                    'keys_count': 0,
                    'active_keys': 0
                }
            users[user_id]['keys_count'] += 1
            if is_key_valid(data):
                users[user_id]['active_keys'] += 1
    
    response = "👥 <b>Пользователи:</b>\n\n"
    for user_id, info in list(users.items())[:20]:
        response += (
            f"👤 {info['username']} (ID: {user_id})\n"
            f"🔑 Ключей: {info['keys_count']} (Активных: {info['active_keys']})\n\n"
        )
    
    if len(users) > 20:
        response += f"\n... и еще {len(users) - 20} пользователей"
    
    bot.send_message(message.chat.id, response, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back_to_main(message):
    """Возврат в главное меню"""
    welcome(message)

# === Проверка ключа через API ===
def validate_key_api(key):
    """Проверяет ключ через API (для использования в HTTP сервере)"""
    keys = load_keys()
    if key not in keys:
        return False
    
    key_data = keys[key]
    return is_key_valid(key_data) and key_data.get('active', True)

# === Запуск бота ===
if __name__ == '__main__':
    print("🤖 Бот запускается...")
    print(f"📁 Файл ключей: {KEYS_FILE}")
    print(f"👑 Админы: {ADMIN_IDS}")
    
    # Создаем файл ключей, если его нет
    if not os.path.exists(KEYS_FILE):
        save_keys({})
        print(f"✅ Создан файл {KEYS_FILE}")
    
    try:
        bot.infinity_polling(none_stop=True, interval=0)
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")

