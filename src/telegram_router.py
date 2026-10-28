"""
Legend Trading AI — Secure Telegram Router (v0.3)
"""
import logging
from functools import wraps
from pathlib import Path
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from src.config import env
from src.signal_db import init_db, log_signal, get_pending_trades
from src.live_features import get_latest_features, fetch_klines
from src.xgb_pure import XGBPure
from src.trade_planner import build_trade_plan
from src.risk_engine import check_circuit_breaker, set_pause

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

AUTHORIZED_USER_IDS = [int(env.get("TELEGRAM_CHAT_ID") or 0)]
MODEL_DIR = Path("models/v0.2")

def format_price(price):
    """Dynamically formats price based on the asset (BTC vs XRP)."""
    if price >= 1000:
        return f"{price:,.2f}" # BTC, ETH
    elif price >= 1:
        return f"{price:.4f}"  # XRP, ADA
    else:
        return f"{price:.6f}"  # SHIB, PEPE

def restricted(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        if user_id not in AUTHORIZED_USER_IDS:
            if update.message: await update.message.reply_text("⛔ Unauthorized access.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("builder", "Force scan: /builder BTCUSDT 1h"),
        BotCommand("trades", "View open PENDING trades"),
        BotCommand("pause", "Halt new trades"),
        BotCommand("resume", "Resume trading"),
    ]
    await application.bot.set_my_commands(commands)

@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    await update.message.reply_text("🤖 LEGEND TRADING AI v0.3\nDatabase ready. Risk Engine active.")

@restricted
async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_pause(True)
    await update.message.reply_text("🛑 SYSTEM PAUSED. The bot will not create new trades.")

@restricted
async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_pause(False)
    await update.message.reply_text("🟢 SYSTEM RESUMED. Risk engine checks are active.")

@restricted
async def trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trades = get_pending_trades()
    if not trades:
        await update.message.reply_text("📭 No open PENDING trades right now.")
        return
    msg = "📋 OPEN TRADES (PENDING)\n━━━━━━━━━━━━━━━━━━━━\n"
    for t in trades:
        msg += f"• [{t['symbol']}] {t['direction']} @ {format_price(t['entry_price'])}\n"
        msg += f"  SL: {format_price(t['stop_loss'])} | TP1: {format_price(t['tp1'])}\n"
        msg += f"  ID: {t['id']} | TF: {t['timeframe']}\n\n"
    await update.message.reply_text(msg)

@restricted
async def builder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("⚠️ Usage: /builder <SYMBOL> <TF>\nExample: /builder XRPUSDT 1h")
        return
    
    symbol = args[0].upper()
    timeframe = args[1].lower()
    
    allowed, risk_msg = check_circuit_breaker()
    if not allowed:
        await update.message.reply_text(risk_msg)
        return

    await update.message.reply_text(f"🔍 Scanning {symbol} on {timeframe}...\n{risk_msg}")

    try:
        model_name = f"v0.2_{symbol}_{timeframe}_h10_long.json"
        model_path = MODEL_DIR / model_name
        
        if not model_path.exists():
            await update.message.reply_text(f"❌ Error: Model `{model_name}` not found.")
            return

        feats, ts_ms = get_latest_features(symbol, timeframe)
        candles = fetch_klines(symbol, timeframe, limit=2)
        entry_price = float(candles[-2][4])
        atr_14 = feats[18] 

        model = XGBPure(model_path)
        proba = model.predict_proba([feats])[0]
        
        direction = "LONG" if proba > 0.5 else "SHORT"
        confidence = proba if proba > 0.5 else (1 - proba)
        
        plan = build_trade_plan(entry_price, direction, atr_14)
        
        sig_id = log_signal(
            symbol=symbol, timeframe=timeframe, direction=direction,
            model_version=model_name, confidence=float(confidence),
            entry_price=plan["entry"], stop_loss=plan["stop_loss"],
            tp1=plan["tp1"], tp2=plan["tp2"], tp3=plan["tp3"]
        )
        
        # Add a warning if confidence is below 62%
        warning = ""
        if confidence < 0.62:
            warning = "⚠️ WEAK SIGNAL: High risk, do not enter.\n\n"

        msg = (
            f"🎯 LEGEND SIGNAL: {symbol} [{timeframe}]\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{warning}"
            f"Direction:  {direction}\n"
            f"Confidence: {confidence*100:.1f}%\n\n"
            f"📊 TRADE PLAN\n"
            f"Entry:      ${format_price(plan['entry'])}\n"
            f"Stop Loss:  ${format_price(plan['stop_loss'])}\n"
            f"TP1:        ${format_price(plan['tp1'])}\n\n"
            f"✅ Saved to DB (ID: {sig_id})"
        )
        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Error during scan: {str(e)}")

def run_router():
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No Telegram token found in .env")
        return
    app = Application.builder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("trades", trades_command))
    app.add_handler(CommandHandler("builder", builder_command))
    logger.info("🚀 Telegram Router is running...")
    app.run_polling()

if __name__ == "__main__":
    run_router()
