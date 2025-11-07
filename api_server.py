"""
HTTP API сервер для проверки ключей
Можно использовать для проверки ключей из клиента
"""
from flask import Flask, request, jsonify
import os
import json
from datetime import datetime

app = Flask(__name__)

# Файл ключей (должен совпадать с bot.py)
KEYS_FILE = os.getenv("KEYS_FILE", "keys.json")

# API ключ для защиты (опционально)
API_SECRET = os.getenv("API_SECRET", "")

def load_keys():
    """Загружает ключи из файла"""
    try:
        if os.path.exists(KEYS_FILE):
            with open(KEYS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки ключей: {e}")
    return {}

def is_key_valid(key_data):
    """Проверяет, не истек ли ключ"""
    if 'expires_at' not in key_data:
        return True  # Бессрочный ключ
    expires_at = datetime.fromisoformat(key_data['expires_at'])
    return datetime.now() < expires_at

@app.route('/api/validate', methods=['POST', 'GET'])
def validate_key():
    """Проверяет ключ"""
    try:
        # Получаем ключ из запроса
        if request.method == 'POST':
            data = request.get_json() or {}
            key = data.get('key', '')
        else:
            key = request.args.get('key', '')
        
        if not key:
            return jsonify({
                'valid': False,
                'error': 'Key is required'
            }), 400
        
        # Проверяем API секрет, если он установлен
        if API_SECRET:
            provided_secret = request.headers.get('X-API-Secret', '')
            if provided_secret != API_SECRET:
                return jsonify({
                    'valid': False,
                    'error': 'Invalid API secret'
                }), 401
        
        keys = load_keys()
        
        if key not in keys:
            return jsonify({
                'valid': False,
                'error': 'Key not found'
            }), 404
        
        key_data = keys[key]
        
        if not key_data.get('active', True):
            return jsonify({
                'valid': False,
                'error': 'Key is inactive'
            }), 403
        
        if not is_key_valid(key_data):
            return jsonify({
                'valid': False,
                'error': 'Key expired'
            }), 403
        
        return jsonify({
            'valid': True,
            'user_id': key_data.get('user_id'),
            'username': key_data.get('username'),
            'expires_at': key_data.get('expires_at')
        }), 200
        
    except Exception as e:
        return jsonify({
            'valid': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Проверка работоспособности сервера"""
    return jsonify({
        'status': 'ok',
        'keys_file': KEYS_FILE,
        'keys_count': len(load_keys())
    }), 200

@app.route('/', methods=['GET'])
def index():
    """Главная страница"""
    return jsonify({
        'service': 'Key Validation API',
        'endpoints': {
            '/api/validate': 'POST/GET - Проверка ключа (параметр: key)',
            '/api/health': 'GET - Проверка работоспособности'
        }
    }), 200

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"🚀 API сервер запускается на {host}:{port}")
    print(f"📁 Файл ключей: {KEYS_FILE}")
    
    app.run(host=host, port=port, debug=False)

