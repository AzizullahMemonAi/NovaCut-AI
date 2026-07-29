import json
import os
import base64
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.config import settings

CONFIG_PATH = os.path.join(settings.TEMP_DIR, 'ai_runtime_config.json')

def _get_fernet():
    # Derive encryption key from SECRET_KEY so it stays consistent across restarts
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b'nova_ai_config', iterations=100000)
    key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
    return Fernet(key)

def _encrypt(value: str) -> str:
    if not value:
        return ''
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()

def _decrypt(value: str) -> str:
    if not value:
        return ''
    try:
        f = _get_fernet()
        return f.decrypt(value.encode()).decode()
    except Exception:
        return ''

DEFAULT_CONFIG = {
    'gemini_api_key': '',
    'groq_api_key': '',
    'gemini_cooldown_until': None,
    'groq_cooldown_until': None,
    'gemini_usage_today': 0,
    'groq_usage_today': 0,
    'usage_date': None
}

GEMINI_DAILY_LIMIT = 1500
GROQ_DAILY_LIMIT = 14400


def _load():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        _save(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
    except Exception:
        return DEFAULT_CONFIG.copy()


def _save(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def get_ai_config() -> dict:
    return _load()


def save_ai_config(config: dict):
    _save({**DEFAULT_CONFIG, **config})


def get_api_keys() -> dict:
    config = get_ai_config()
    env_gemini = (getattr(settings, 'GEMINI_API_KEY', '') or '').strip()
    runtime_gemini = _decrypt(config.get('gemini_api_key', '').strip())
    gemini_key = env_gemini or runtime_gemini

    env_groq = (getattr(settings, 'GROQ_API_KEY', '') or '').strip()
    runtime_groq = _decrypt(config.get('groq_api_key', '').strip())
    groq_key = env_groq or runtime_groq

    return {
        'gemini_api_key': gemini_key,
        'groq_api_key': groq_key
    }


def save_api_keys(gemini_api_key: str, groq_api_key: str):
    config = get_ai_config()
    config['gemini_api_key'] = _encrypt(gemini_api_key.strip())
    config['groq_api_key'] = _encrypt(groq_api_key.strip())
    save_ai_config(config)


def get_cooldown_times() -> dict:
    config = get_ai_config()
    return {
        'gemini_cooldown_until': config.get('gemini_cooldown_until'),
        'groq_cooldown_until': config.get('groq_cooldown_until')
    }


def save_cooldown(api_name: str, cooldown_until: str | None):
    config = get_ai_config()
    config[f'{api_name}_cooldown_until'] = cooldown_until
    save_ai_config(config)


def is_in_cooldown(api_name: str) -> bool:
    config = get_ai_config()
    raw = config.get(f'{api_name}_cooldown_until')
    if not raw:
        return False
    try:
        dt = datetime.fromisoformat(raw)
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False


def get_cooldown_status() -> dict:
    config = get_ai_config()
    now = datetime.now(timezone.utc)
    status = {}
    for name in ['gemini', 'groq']:
        raw = config.get(f'{name}_cooldown_until')
        try:
            dt = datetime.fromisoformat(raw) if raw else None
        except Exception:
            dt = None
        status[name] = {
            'cooldown_until': dt.isoformat() if dt else None,
            'is_in_cooldown': bool(dt and dt > now)
        }
    return status


def _check_reset_usage(config: dict):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if config.get('usage_date') != today:
        config['usage_date'] = today
        config['gemini_usage_today'] = 0
        config['groq_usage_today'] = 0


def increment_usage(api_name: str):
    config = get_ai_config()
    _check_reset_usage(config)
    key = f'{api_name}_usage_today'
    config[key] = config.get(key, 0) + 1
    save_ai_config(config)


def get_usage_status() -> dict:
    config = get_ai_config()
    _check_reset_usage(config)
    save_ai_config(config)
    
    gemini_used = config.get('gemini_usage_today', 0)
    groq_used = config.get('groq_usage_today', 0)
    
    return {
        'gemini': {
            'used': gemini_used,
            'limit': GEMINI_DAILY_LIMIT,
            'remaining': max(0, GEMINI_DAILY_LIMIT - gemini_used)
        },
        'groq': {
            'used': groq_used,
            'limit': GROQ_DAILY_LIMIT,
            'remaining': max(0, GROQ_DAILY_LIMIT - groq_used)
        }
    }
