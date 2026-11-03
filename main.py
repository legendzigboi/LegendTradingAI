"""
LEGEND TRADING AI - PXXL / GUNICORN COMPATIBLE
"""
import os
import asyncio
import threading
import logging
from flask import Flask
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from src.config import env
from src.telegram_router import start_command, signals_command, button_handler
from src.lifecycle_tracker import check_trades

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. The Flask app (for Pxxl's health check)
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Legend Trading AI is ALIVE!", 200

# 2. The Telegram Bot logic (runs in a background thread)
def run_bot():
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ No Telegram token found!")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot_app = Application.builder().token(token).post_init(lambda x: x.bot.set_my_commands([("start", "Open Main Menu")])).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("signals", signals_command))
    bot_app.add_handler(CallbackQueryHandler(button_handler))

    bot_app.job_queue.run_repeating(check_trades, interval=300, first=10)
    
    # We use polling here. Pxxl's dedicated CPU will make it fast.
    logger.info("🚀 Bot is starting polling...")
    bot_app.run_polling()

# 3. Start the bot thread as soon as Gunicorn imports this file
threading.Thread(target=run_bot, daemon=True).start()

# 4. Gunicorn will automatically use the `app` variable above to serve the website.
