"""
Legend Trading AI — Secure Telegram Router (v0.3)
"""
import logging
from functools import wraps
from pathlib import Path
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from src.config import env
from src.signal_db import stats_last_n_days
from src.live_features import get_latest_features
from src.xgb_pure import XGBPure

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

AUTHORIZED_USER_IDS = [int(env.get("TELEGRAM_CHAT_ID", 0))]
MODEL_DIR = Path("models/v0.2")

def restricted(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        if user_id not in AUTHORIZED_USER_IDS:
            if update.message:
                await update.message.reply_text("⛔ Unauthorized access.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- SETUP COMMAND MENU ---
async def post_init(application: Application) -> None:
    """Sets the command menu that appears on the left of the Telegram chat bar."""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("builder", "Force scan: /builder BTCUSDT 1h"),
        BotCommand("signals", "Low-risk aligned setups"),
        BotCommand("status", "Check bot health"),
        BotCommand("results", "View PnL & win rate"),
    ]
    await application.bot.set_my_commands(commands)

@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 LEGEND TRADING AI v0.3\n\nUse the Menu button on the left or type /builder to scan a market.")

@restricted
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 Status: ONLINE\nEngine: READY")

@restricted
async def builder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("⚠️ Usage: /builder <SYMBOL> <TF>\nExample: /builder XRPUSDT 1h")
        return
    
    symbol = args[0].upper()
    timeframe = args[1].lower()
    
    await update.message.reply_text(f"🔍 Scanning {symbol} on {timeframe}...")

    try:
        feats, ts_ms = get_latest_features(symbol, timeframe)
        
        # Defaulting to H=10 long model for the test
        model_name = f"v0.2_{symbol}_h10_long.json"
        model_path = MODEL_DIR / model_name
        
        if not model_path.exists():
            await update.message.reply_text(f"❌ Error: Model `{model_name}` not found.")
            return

        model = XGBPure(model_path)
        proba = model.predict_proba([feats])[0]
        
        direction = "LONG" if proba > 0.5 else "SHORT"
        confidence = proba if proba > 0.5 else (1 - proba)
        
        msg = (
            f"🎯 LEGEND SIGNAL: {symbol}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Direction:  {direction}\n"
            f"Confidence: {confidence*100:.1f}%\n"
            f"Timeframe:  {timeframe}\n"
            f"Model:      {model_name}\n"
        )
        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Error during scan: {str(e)}")

@restricted
async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = stats_last_n_days(days=1)
    if not stats:
        await update.message.reply_text("📊 No trades settled today.")
        return
    msg = "📊 TODAY'S RESULTS\n━━━━━━━━━━━━━━━━━━━━\n"
    for row in stats:
        msg += f"• {row['symbol']} {row['direction'].upper()}: {row['wins']}/{row['trades']} wins\n"
    await update.message.reply_text(msg)

def run_router():
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No Telegram token found in .env")
        return
        
    # Note the post_init=post_init here. This pushes the menu to Telegram.
    app = Application.builder().token(token).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("builder", builder_command))
    app.add_handler(CommandHandler("results", results_command))
    
    logger.info("🚀 Telegram Router is running...")
    app.run_polling()

if __name__ == "__main__":
    run_router()
