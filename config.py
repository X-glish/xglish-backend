"""
Xglish Configuration System
Stores user preferences in ~/.xglish/config.json
"""
import json
import os
from pathlib import Path

# Default configuration
DEFAULT_CONFIG = {
    "translation_model": "libretranslate",  # or "indictrans2"
    "hf_token": "",  # Hugging Face access token for IndicTrans2
    "indictrans_model": "ai4bharat/indictrans2-en-indic-dist-200M",
    "libretranslate_languages": ["en"],
    "formality_threshold": 7,
    "server_port": 5050,
}

def get_config_dir():
    """Get config directory path (~/.xglish)"""
    return Path.home() / ".xglish"

def get_config_path():
    """Get config file path (~/.xglish/config.json)"""
    return get_config_dir() / "config.json"

def ensure_config_dir():
    """Create config directory if it doesn't exist"""
    config_dir = get_config_dir()
    config_dir.mkdir(exist_ok=True)
    return config_dir

def load_config():
    """Load configuration from home directory, create if missing"""
    ensure_config_dir()
    config_path = get_config_path()
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
            # Merge with defaults (in case new fields were added)
            config = DEFAULT_CONFIG.copy()
            config.update(user_config)
            return config
        except Exception as e:
            print(f"Warning: Failed to load config: {e}. Using defaults.")
            return DEFAULT_CONFIG.copy()
    else:
        # Create default config file
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to home directory"""
    ensure_config_dir()
    config_path = get_config_path()
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def get_translation_model():
    """Get current translation model selection"""
    config = load_config()
    return config.get("translation_model", "libretranslate")

def get_hf_token():
    """Get Hugging Face token"""
    config = load_config()
    return config.get("hf_token", "")

def update_config(key, value):
    """Update a single config value"""
    config = load_config()
    config[key] = value
    save_config(config)

# Initialize config on import
_config = load_config()
