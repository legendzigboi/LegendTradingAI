"""
Legend Trading AI — Telegram Bot

Sends messages to your Telegram chat via the Bot API.

Usage (test):
    python -m src.telegram_bot

Requires .env with:
    TELEGRAM_BOT_TOKEN=...
    TELEGRAM_CHAT_ID=...
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# ------------------------------------------------------------
# Load .env from project root
# ------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ------------------------------------------------------------
# Send a plain text message
# ------------------------------------------------------------
def send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """
    Send a Telegram message.

    Args:
        text: message body (Markdown supported)
        parse_mode: "Markdown", "MarkdownV2", "HTML", or None

    Returns:
        True if sent successfully, False otherwise.
    """
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
        return False

    url = f"{API_BASE}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            print(f"Telegram API error: {r.status_code}")
            print(r.text)
            return False
        return True
    except Exception as e:
        print(f"Request failed: {e}")
        return False


# ------------------------------------------------------------
# Self-test (run: python -m src.telegram_bot)
# ------------------------------------------------------------
if __name__ == "__main__":
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    message = (
        "🤖 *LEGEND TRADING AI*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ System is ONLINE\n\n"
        f"Time: `{now}`\n"
        "Status: TEST MESSAGE\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Your bot is working.\n"
        "Real signals will arrive here."
    )

    print("Sending test message to Telegram...")
    ok = send_message(message)
    print("Sent ✅" if ok else "Failed ❌")
