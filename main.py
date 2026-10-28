"""
LEGEND TRADING AI - MASTER LOCAL ENGINE
"""
import logging
from telegram.ext import Application, CommandHandler
from src.config import env
from src.telegram_router import post_init, start_command, pause_command, resume_command, trades_command, builder_command
from src.lifecycle_tracker import check_trades

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No Telegram token found in .env")
        return

    app = Application.builder().token(token).post_init(post_init).build()

    # Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("trades", trades_command))
    app.add_handler(CommandHandler("builder", builder_command))

    # Background Lifecycle Tracker (every 5 mins)
    app.job_queue.run_repeating(check_trades, interval=300, first=10)

    logger.info("🚀 Legend Trading AI Master Engine is running LOCALLY...")
    app.run_polling()

if __name__ == "__main__":
    main()
