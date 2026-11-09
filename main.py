"""
LEGEND TRADING AI - CLOUD ENGINE (Render Compatible)
"""
import os
import asyncio
import threading
import logging
from flask import Flask
from datetime import time
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from src.config import env
from src.signal_db import init_db
from src.telegram_router import start_command, signals_command, button_handler
from src.lifecycle_tracker import check_trades

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Create the fake website for Render's health check
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Legend Trading AI is ALIVE!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# 2. Wrapper for scheduled scans
async def scheduled_scan_job(context):
    await signals_command(None, context)

# 3. Error handler to catch crashes
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

# 4. Run the Bot
def run_bot():
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ No Telegram token found!")
        return

    init_db()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot_app = Application.builder().token(token).post_init(lambda x: x.bot.set_my_commands([("start", "Open Main Menu")])).build()

    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("signals", signals_command))
    bot_app.add_handler(CallbackQueryHandler(button_handler))

    bot_app.add_error_handler(error_handler)

    # Background Jobs
    bot_app.job_queue.run_repeating(check_trades, interval=300, first=10)
    bot_app.job_queue.run_daily(scheduled_scan_job, time=time(hour=7, minute=0))
    bot_app.job_queue.run_daily(scheduled_scan_job, time=time(hour=13, minute=0))
    bot_app.job_queue.run_daily(scheduled_scan_job, time=time(hour=19, minute=0))
    
    # 🚨 START THE 3-DAY AUTO-TRADER 🚨
    # Runs once, 10 seconds after the bot boots up.

    logger.info("🚀 Bot is starting polling...")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()
