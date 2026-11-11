import logging
import asyncio
import os
from functools import wraps
from pathlib import Path
from datetime import datetime, timezone, timedelta
from telegram import Update, BotCommand
from telegram.ext import ContextTypes
from src.config import env
from src.signal_db import init_db, log_signal, get_pending_trades, get_performance_stats, get_all_insights, get_historical_win_rate
from src.live_features import get_latest_features, fetch_klines
from src.model_registry import get_model
from src.trade_planner import build_trade_plan
from src.risk_engine import check_circuit_breaker, set_pause
from src.state import SYSTEM_PAUSED
from src.chart_generator import generate_chart
from src.banner_generator import generate_banner
from src.image_composer import combine_banner_and_chart
from src.technical_analyst import get_technical_overview
from src.telegram_keyboards import get_main_menu, get_market_menu, get_crypto_menu, get_forex_menu, get_stocks_menu, get_indices_menu, get_timeframe_menu
from src.engines.fusion_engine import FusionEngine
from src.engines.base_engine import TrendEngine
from src.research_engine import run_research_lab
from src.news_filter import check_high_impact_news
from src.sentiment_engine import get_market_sentiment
from src.deep_researcher import deep_research_trade
from src.sr_engine import check_support_resistance
from src.fear_greed_engine import get_crypto_fear_greed
from src.regime_engine import check_market_regime
from src.order_flow_engine import get_order_flow_imbalance, calculate_vwap_zscore
from src.macro_engine import get_crypto_crowd_sentiment, get_dxy_trend, get_us10y_trend, get_spx_trend
from src.kelly_engine import calculate_kelly_position_size
from src.price_sync import adjust_plan_to_live_price
from src.auto_trader import CRYPTO, FOREX_STOCKS, TIMEFRAMES

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

AUTHORIZED_USER_IDS = [int(env.get("TELEGRAM_CHAT_ID") or 0)]
MODEL_DIR = Path("models/v0.2")
MIN_CONFIDENCE = 0.60 
WAT = timezone(timedelta(hours=1))

analysis_lock = asyncio.Lock()
scan_lock = asyncio.Lock()

def format_price(price):
    if price >= 1000: return f"{price:,.2f}"
    elif price >= 1: return f"{price:.4f}"
    else: return f"{price:.6f}"

def restricted(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update:
            user_id = update.effective_user.id if update.effective_user else None
            if user_id not in AUTHORIZED_USER_IDS:
                if update.message: await update.message.reply_text("⛔ Unauthorized.")
                elif update.callback_query: await update.callback_query.answer("⛔ Unauthorized", show_alert=True)
                return
        return await func(update, context, *args, **kwargs)
    return wrapped

async def post_init(application) -> None:
    await application.bot.set_my_commands([BotCommand("start", "Open Main Menu")])

@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    text = "🤖 LEGEND TRADING AI PREMIUM\n━━━━━━━━━━━━━━━━━━━━\nWelcome. Select an option below:"
    await update.message.reply_text(text, reply_markup=get_main_menu())

async def run_full_scan_task(chat_id, bot):
    all_symbols = CRYPTO + FOREX_STOCKS
    valid_results = []
    
    for symbol in all_symbols:
        for tf in TIMEFRAMES:
            try:
                if tf == "FUSION":
                    engine = FusionEngine()
                    res = await asyncio.to_thread(engine.analyze, symbol)
                else:
                    engine = TrendEngine()
                    res = await asyncio.to_thread(engine.analyze, symbol, tf)
                    
                if "error" not in res and res.get("status") == "SUCCESS":
                    if res["confidence"] >= MIN_CONFIDENCE:
                        valid_results.append(res)
                        
                await asyncio.sleep(1.5) # Prevent API bans
            except Exception as e:
                logger.error(f"Scan error {symbol} {tf}: {e}")

    if not valid_results:
        await bot.send_message(chat_id=chat_id, text="⚪ **SCAN COMPLETE**\n\nNo setups passed the 60% confidence threshold across all markets right now. The Sniper is waiting for a better shot.", parse_mode="Markdown")
        return

    # Sort by highest confidence
    valid_results.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Take the top 3
    top_signals = valid_results[:3]
    
    await bot.send_message(chat_id=chat_id, text=f"🎯 **SCAN COMPLETE!**\nFound {len(valid_results)} high-confidence setups. Sending the Top {len(top_signals)} now...", parse_mode="Markdown")

    for res in top_signals:
        symbol = res["symbol"]
        direction = res["direction"]
        confidence = res["confidence"]
        plan = res["plan"]
        display_tf = res["timeframe"]
        model_name = res["engine"]
        
        sig_id = log_signal(symbol=symbol, timeframe=display_tf, direction=direction, model_version=model_name, confidence=float(confidence), entry_price=plan["entry"], stop_loss=plan["stop_loss"], tp1=plan["tp1"], tp2=plan.get("tp2", 0), tp3=plan.get("tp3", 0))
        
        msg = (
            f"🤖 **LEGEND SCANNER ALERT**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{'🟢 BUY ▲' if direction == 'LONG' else '🔴 SELL ▼'}\n"
            f"{symbol} · {display_tf}\n"
            f"Engine: {model_name}\n\n"
            f"📊 CONFIDENCE: {confidence*100:.1f}%\n"
            f"⏱ EXPIRY: {plan['duration_min']} minutes\n\n"
            f"🎯 TRADE PLAN\n"
            f"Entry: <code>{format_price(plan['entry'])}</code>\n"
            f"SL: <code>{format_price(plan['stop_loss'])}</code>\n"
            f"Target: <code>{format_price(plan['tp1'])}</code>\n\n"
            f"ID: {sig_id}"
        )
        await bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")


@restricted
async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id if update and update.effective_chat else AUTHORIZED_USER_IDS[0]
    
    if scan_lock.locked():
        await context.bot.send_message(chat_id=chat_id, text="⏳ A scan is already in progress. Please wait for it to finish.")
        return
        
    await context.bot.send_message(chat_id=chat_id, text="🔍 **GOD MODE SCAN STARTED**\n\nScanning ALL Crypto, Forex, Stocks, and Indices across ALL Timeframes (1m to 1d + Fusion). This will take about 2-3 minutes. I will message you the Top 3 highest-confidence setups when I'm done! 📊")
    
    async with scan_lock:
        asyncio.create_task(run_full_scan_task(chat_id, context.bot))

# ... (Insert the standard `run_analysis` function here from previous versions) ...
# ... (Because it's long, I will assume you still have it in your file. If not, let me know) ...

@restricted
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'menu_main':
        await query.edit_message_text("🤖 MAIN MENU\nSelect an option:", reply_markup=get_main_menu())
    elif query.data == 'menu_market':
        await query.edit_message_text("💹 SELECT MARKET:", reply_markup=get_market_menu())
    elif query.data == 'market_crypto':
        await query.edit_message_text("🪙 SELECT CRYPTO PAIR:", reply_markup=get_crypto_menu())
    elif query.data == 'market_forex':
        await query.edit_message_text("💱 SELECT FOREX PAIR:", reply_markup=get_forex_menu())
    elif query.data == 'market_stocks':
        await query.edit_message_text("📈 SELECT STOCK:", reply_markup=get_stocks_menu())
    elif query.data == 'market_indices':
        await query.edit_message_text("📊 SELECT INDEX/METAL:", reply_markup=get_indices_menu())
    elif query.data == 'menu_signals':
        await signals_command(update, context)
    elif query.data == 'menu_pause':
        set_pause(True)
        await query.edit_message_text("🛑 SYSTEM PAUSED.", reply_markup=get_main_menu())
    elif query.data == 'menu_resume':
        set_pause(False)
        await query.edit_message_text("🟢 SYSTEM RESUMED.", reply_markup=get_main_menu())
    elif query.data == 'menu_research':
        await query.edit_message_text("🔬 Running Research Lab...", reply_markup=None)
        result = await asyncio.to_thread(run_research_lab)
        await query.edit_message_text(result, reply_markup=get_main_menu())
    elif query.data == 'menu_memory':
        insights = get_all_insights()
        if not insights:
            text = "🧠 **AI MEMORY IS EMPTY**"
        else:
            text = "🧠 **AI MEMORY**\n\n"
            for i in insights:
                emoji = "🔴" if i['category'] == "AUTO_AUTOPSY" else "📊"
                text += f"{emoji} {i['insight']}\n*(Sample: {i['sample_size']})*\n\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu())
    elif query.data == 'menu_testing':
        await query.edit_message_text("⚙️ **MODEL TESTING**\n\nComing Soon.", parse_mode="Markdown", reply_markup=get_main_menu())
    elif query.data == 'menu_status':
        await query.edit_message_text("🤖 **SYSTEM STATUS**\n\nAll systems operational.", parse_mode="Markdown", reply_markup=get_main_menu())
    elif query.data == 'menu_performance':
        stats = get_performance_stats()
        text = (
            f"📊 PERFORMANCE\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Closed: {stats['total_closed']}\n"
            f"✅ Wins: {stats['wins']}\n"
            f"❌ Losses: {stats['losses']}\n"
            f"⏱ Expired: {stats['expired']}\n"
            f"🏆 Win Rate: {stats['win_rate']:.1f}%\n"
            f"⏳ Pending: {stats['pending']}"
        )
        await query.edit_message_text(text, reply_markup=get_main_menu())
    elif query.data.startswith('pair_'):
        symbol = query.data.split('_', 1)[1] 
        await query.edit_message_text(f"⏱️ SELECT TIMEFRAME FOR {symbol}:", reply_markup=get_timeframe_menu(symbol))
    elif query.data.startswith('tf_'):
        if analysis_lock.locked():
            await query.answer("⏳ AI is analyzing. Please wait.", show_alert=True); return
        parts = query.data.split('_')
        tf_type, symbol = parts[1], parts[2]
        async with analysis_lock:
            await query.edit_message_text(f"🔍 Analyzing {symbol} on {tf_type}...", reply_markup=None)
            await run_analysis(query.message, symbol, tf_type)
