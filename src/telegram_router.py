"""
Legend Trading AI — Secure Telegram Router (v0.3)

Pillar 1: Security Whitelist (Only authorized users can command the bot)
Pillar 6: Interface (Telegram is the control panel, not the brain)
"""
import logging
from functools import wraps
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from src.config import env
from src.signal_db import stats_last_n_days

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- PILLAR 1: SECURITY WHITELIST ---
# We use numeric Telegram User IDs, not usernames.
# This pulls your Chat ID from the .env file.
AUTHORIZED_USER_IDS = [int(env.get("TELEGRAM_CHAT_ID", 0))]

def restricted(func):
    """Decorator to ensure only the owner can use the bot."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Safe check for user ID
        user_id = update.effective_user.id if update.effective_user else None
        
        if user_id not in AUTHORIZED_USER_IDS:
            logger.warning(f"Unauthorized access attempt by ID: {user_id}")
            if update.message:
                await update.message.reply_text("⛔ Unauthorized access. This incident has been logged.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- COMMANDS ---

@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 LEGEND TRADING AI v0.3\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "I am your institutional paper-trading engine.\n\n"
        "Commands:\n"
        "/status - Feed health & engine state\n"
        "/signals - Scan for strictly aligned setups\n"
        "/builder <SYMBOL> <TF> - Force scan (e.g. /builder XRPUSDT 5m)\n"
        "/trades - View open paper trades\n"
        "/results - View PnL & win rate\n"
        "/pause - Halt new trades\n"
        "/resume - Resume after safety checks\n"
        "/health - API & DB status"
    )
    await update.message.reply_text(msg)

@restricted
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Placeholder for now. Later, this checks Pillar 2 & 3 (Feed Health & Circuit Breakers)
    await update.message.reply_text("🟢 Status: ONLINE\nEngine: READY\nFeed: Checking...")

@restricted
async def builder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("⚠️ Usage: /builder <SYMBOL> <TIMEFRAME>\nExample: /builder XRPUSDT 5m")
        return
    
    symbol = args[0].upper()
    timeframe = args[1].lower()
    
    await update.message.reply_text(f"🔍 Scanning {symbol} on {timeframe}...\n(⚠️ High risk mode: Bypassing multi-timeframe alignment, but NOT risk limits)")

    # TODO: Call the signal engine here
    # 1. Check Data Health (Feed must be fresh)
    # 2. Call live_features.get_latest_features(symbol, timeframe)
    # 3. Load appropriate model from registry
    # 4. Return formatted signal

@restricted
async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = stats_last_n_days(days=1)
    if not stats:
        await update.message.reply_text("📊 No trades settled today.")
        return
    
    msg = "📊 TODAY'S RESULTS\n━━━━━━━━━━━━━━━━━━━━\n"
    for row in stats:
        msg += f"• {row['symbol']} {row['direction'].upper()}: {row['wins']}/{row['trades']} wins (Avg: {row['avg_return']*100:.2f}%)\n"
    
    await update.message.reply_text(msg)

def run_router():
    """Start the Telegram polling loop."""
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No Telegram token found in .env")
        return

    app = Application.builder().token(token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("builder", builder_command))
    app.add_handler(CommandHandler("results", results_command))
    
    # We will add /signals, /trades, /pause, /resume as we build the pillars

    logger.info("🚀 Telegram Router is running...")
    app.run_polling()

if __name__ == "__main__":
    run_router()
