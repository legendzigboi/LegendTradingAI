import logging
from datetime import time
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from src.config import env
from src.telegram_router import start_command, signals_command, button_handler
from src.lifecycle_tracker import check_trades

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No Telegram token found in .env")
        return

    app = Application.builder().token(token).post_init(lambda x: x.bot.set_my_commands([("start", "Open Main Menu")])).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.job_queue.run_repeating(check_trades, interval=300, first=10)
    app.job_queue.run_daily(signals_command, time=time(hour=7, minute=0))  
    app.job_queue.run_daily(signals_command, time=time(hour=13, minute=0)) 
    app.job_queue.run_daily(signals_command, time=time(hour=19, minute=0)) 

    logger.info("🚀 Legend Trading AI Premium (Fusion Engines) is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
