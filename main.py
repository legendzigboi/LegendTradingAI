"""
LEGEND TRADING AI - CLOUD WEB WRAPPER
Runs the bot in a background thread and a Flask server to keep the port alive.
"""
import os
import threading
import logging
from flask import Flask
from telegram.ext import Application, CommandHandler

from src.config import env
from src.telegram_router import post_init, start_command, pause_command, resume_command, trades_command, builder_command
from src.lifecycle_tracker import check_trades

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Create the Flask app for Cloady's health checks
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Legend Trading AI is ALIVE!", 200

# 2. The actual bot logic
def run_bot():
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No Telegram token found.")
        return

    bot_app = Application.builder().token(token).post_init(post_init).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("pause", pause_command))
    bot_app.add_handler(CommandHandler("resume", resume_command))
    bot_app.add_handler(CommandHandler("trades", trades_command))
    bot_app.add_handler(CommandHandler("builder", builder_command))

    bot_app.job_queue.run_repeating(check_trades, interval=300, first=10)

    logger.info("🚀 Bot thread started...")
    bot_app.run_polling()

# 3. Start everything
if __name__ == "__main__":
    # Start the bot in a separate thread
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Start the Flask server (Cloady requires binding to the PORT env variable)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
