"""
LEGEND TRADING AI - MASTER CLOUD ENGINE
Runs the Telegram Router and the Lifecycle Tracker in one process.
"""
import logging
from telegram.ext import Application
from src.config import env
from src.telegram_router import post_init, start_command, pause_command, resume_command, trades_command, builder_command
from src.lifecycle_tracker import check_trades
from telegram.ext import CommandHandler

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No Telegram token found in .env")
        return

    # Build the application
    app = Application.builder().token(token).post_init(post_init).build()

    # Add Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("trades", trades_command))
    app.add_handler(CommandHandler("builder", builder_command))

    # Setup JobQueue (runs the lifecycle tracker every 300 seconds / 5 mins)
    job_queue = app.job_queue
    job_queue.run_repeating(check_trades, interval=300, first=10)

    logger.info("🚀 Legend Trading AI Master Engine is running...")
    
    # Start polling
    app.run_polling()

if __name__ == "__main__":
    main()
