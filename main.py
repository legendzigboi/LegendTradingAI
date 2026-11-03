"""
LEGEND TRADING AI - CLOUD ENGINE (Bot in Main Thread)
"""
import os
import threading
import logging
from flask import Flask
from datetime import time
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

def run_flask():
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

# 2. Start everything
if __name__ == "__main__":
    # Start Flask in a background daemon thread
    threading.Thread(target=run_flask, daemon=True).start()

    # Run the Bot in the MAIN thread so errors show up in Cloady
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ No Telegram token found in Environment Variables!")
        exit(1)

    bot_app = Application.builder().token(token).post_init(lambda x: x.bot.set_my_commands([("start", "Open Main Menu")])).build()
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("signals", signals_command))
    bot_app.add_handler(CallbackQueryHandler(button_handler))

    # Background Jobs
    bot_app.job_queue.run_repeating(check_trades, interval=300, first=10)
    bot_app.job_queue.run_daily(signals_command, time=time(hour=7, minute=0))
    bot_app.job_queue.run_daily(signals_command, time=time(hour=13, minute=0))
    bot_app.job_queue.run_daily(signals_command, time=time(hour=19, minute=0))

    logger.info("🚀 Bot is starting polling...")
    bot_app.run_polling()
