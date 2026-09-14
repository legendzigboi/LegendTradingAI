"""
Legend Trading AI — Configuration Loader

Loads settings from:
  - config/settings.yaml  (non-secret settings)
  - .env                  (secrets: Telegram token, etc.)

Any other module imports from here, e.g.:
    from src.config import settings, env
"""

from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "settings.yaml"
ENV_PATH = ROOT / ".env"

# ------------------------------------------------------------
# Load .env (silent if missing — CI/servers may inject vars)
# ------------------------------------------------------------
load_dotenv(dotenv_path=ENV_PATH)

# ------------------------------------------------------------
# Load settings.yaml
# ------------------------------------------------------------
def _load_settings() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

settings: dict = _load_settings()

# ------------------------------------------------------------
# Expose environment variables as a simple dict
# ------------------------------------------------------------
env: dict = {
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "TELEGRAM_CHAT_ID":   os.getenv("TELEGRAM_CHAT_ID", ""),
    "DATA_API_KEY":       os.getenv("DATA_API_KEY", ""),
    "ENV":                os.getenv("ENV", "development"),
    "LOG_LEVEL":          os.getenv("LOG_LEVEL", "INFO"),
    "DB_PATH":            os.getenv("DB_PATH", "data/legend.db"),
}

# ------------------------------------------------------------
# Quick self-test (run: python -m src.config)
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Config loaded OK")
    print(f"  settings.app.name      = {settings.get('app', {}).get('name')}")
    print(f"  settings.model.mode    = {settings.get('model', {}).get('mode')}")
    print(f"  TELEGRAM_CHAT_ID set:  {bool(env['TELEGRAM_CHAT_ID'])}")
    print(f"  TELEGRAM_TOKEN set:    {bool(env['TELEGRAM_BOT_TOKEN'])}")
