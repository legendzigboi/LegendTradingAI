"""
LEGEND TRADING AI - CLOUD WEB WRAPPER
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

# 1. Create the fake website for Cloady
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Legend Trading AI is ALIVE!", 200

# 2. Run the bot in the background
def run_bot():
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No Telegram token found.")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot_app = Application.builder().token(token).post_init(lambda x: x.bot.set_my_commands([("start", "Open Main Menu")])).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("signals", signals_command))
    bot_app.add_handler(CallbackQueryHandler(button_handler))

    bot_app.job_queue.run_repeating(check_trades, interval=300, first=10)
    bot_app.job_queue.run_daily(signals_command, time=__import__('datetime').time(hour=7, minute=0))
    bot_app.job_queue.run_daily(signals_command, time=__import__('datetime').time(hour=13, minute=0))
    bot_app.job_queue.run_daily(signals_command, time=__import__('datetime').time(hour=19, minute=0))

    logger.info("🚀 Bot thread started...")
    bot_app.run_polling()

# 3. Start both
if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Cloady requires binding to the PORT environment variable (usually 3000 or 8000)
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
