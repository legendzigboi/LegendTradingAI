"""
LEGEND TRADING AI - CLOUD WEB WRAPPER (Asyncio Fixed)
"""
import os
import asyncio
import threading
import logging
from flask import Flask
from telegram.ext import Application, CommandHandler

from src.config import env
from src.telegram_router import post_init, start_command, pause_command, resume_command, trades_command, builder_command
from src.lifecycle_tracker import check_trades

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def health_check():
    return "Legend Trading AI is ALIVE!", 200

def run_bot():
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No Telegram token found.")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot_app = Application.builder().token(token).post_init(post_init).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("pause", pause_command))
    bot_app.add_handler(CommandHandler("resume", resume_command))
    bot_app.add_handler(CommandHandler("trades", trades_command))
    bot_app.add_handler(CommandHandler("builder", builder_command))

    bot_app.job_queue.run_repeating(check_trades, interval=300, first=10)

    logger.info("🚀 Bot thread started and polling...")
    bot_app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
