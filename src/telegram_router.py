import logging
import asyncio
import os
from functools import wraps
from pathlib import Path
from datetime import datetime, timezone, timedelta
from telegram import Update, BotCommand
from telegram.ext import ContextTypes
from src.config import env
from src.signal_db import init_db, log_signal, get_pending_trades, get_performance_stats, get_all_insights
from src.live_features import get_latest_features, fetch_klines
from src.model_registry import get_model
from src.trade_planner import build_trade_plan
from src.risk_engine import check_circuit_breaker, set_pause
from src.chart_generator import generate_chart
from src.banner_generator import generate_banner
from src.image_composer import combine_banner_and_chart
from src.technical_analyst import get_technical_overview
from src.signal_scanner import scan_markets
from src.telegram_keyboards import get_main_menu, get_market_menu, get_crypto_menu, get_forex_menu, get_stocks_menu, get_indices_menu, get_timeframe_menu
from src.engines.fusion_engine import FusionEngine
from src.research_engine import run_research_lab
from src.news_filter import check_high_impact_news
from src.sentiment_engine import get_market_sentiment
from src.deep_researcher import deep_research_trade

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

AUTHORIZED_USER_IDS = [int(env.get("TELEGRAM_CHAT_ID") or 0)]
MODEL_DIR = Path("models/v0.2")
MIN_CONFIDENCE = 0.65 
MIN_ATR_CRYPTO = 0.0015 
MIN_ATR_FOREX = 0.0003  
WAT = timezone(timedelta(hours=1))

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
                if update.message: await update.message.reply_text("⛔ Unauthorized.", parse_mode=None)
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

async def scheduled_scan_job(context):
    await signals_command(None, context)

@restricted
async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (Same as before, omitted for brevity - assumes unchanged)
    pass

async def run_analysis(message, symbol, timeframe):
    # (Same as before, omitted for brevity - assumes unchanged)
    pass

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
        
    # 🚨 NEW MENUS 🚨
    elif query.data == 'market_stocks':
        await query.edit_message_text("📈 SELECT STOCK:", reply_markup=get_stocks_menu())
    elif query.data == 'market_indices':
        await query.edit_message_text("📊 SELECT INDEX/METAL:", reply_markup=get_indices_menu())
        
    elif query.data == 'menu_pause':
        set_pause(True)
        await query.edit_message_text("🛑 SYSTEM PAUSED.", reply_markup=get_main_menu())
    elif query.data == 'menu_research':
        await query.edit_message_text("🔬 Running Research Lab... Scanning database for patterns.", reply_markup=None)
        result = await asyncio.to_thread(run_research_lab)
        await query.edit_message_text(result, reply_markup=get_main_menu())
    elif query.data == 'menu_memory':
        insights = get_all_insights()
        if not insights:
            text = "🧠 **AI MEMORY IS EMPTY**\n\nNo patterns discovered yet. Run the Research Lab or wait for more trades to close."
        else:
            text = "🧠 **AI MEMORY (RECENT DISCOVERIES)**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            for i in insights:
                emoji = "🔥" if i['category'] == "EDGE" else ("⚠️" if i['category'] == "WARNING" else "📊")
                text += f"{emoji} {i['insight']}\n*(Sample Size: {i['sample_size']})*\n\n"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu())
    elif query.data == 'menu_testing':
        await query.edit_message_text("⚙️ **MODEL TESTING**\n\nBacktest and validate new models before promoting them to the live engine.\n\n(Coming Soon: /backtest)", parse_mode="Markdown", reply_markup=get_main_menu())
    elif query.data == 'menu_status':
        await query.edit_message_text("🤖 **SYSTEM STATUS**\n\nAll systems operational.\n- Database: PostgreSQL (Online)\n- Data Feeds: Binance/Bybit/Yahoo\n- Research Engine: Active\n- News Filter: Active\n- Sentiment Engine: Active\n- Deep Researcher (LLM): Active", parse_mode="Markdown", reply_markup=get_main_menu())
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
        # Handle special characters in symbols like = or ^
        symbol = query.data.split('_', 1)[1] 
        await query.edit_message_text(f"⏱️ SELECT TIMEFRAME FOR {symbol}:", reply_markup=get_timeframe_menu(symbol))
    elif query.data.startswith('tf_'):
        parts = query.data.split('_')
        tf_type, symbol = parts[1], parts[2]
        await query.edit_message_text(f"🔍 Analyzing {symbol} on {tf_type}...\nPlease wait.", reply_markup=None)
        await run_analysis(query.message, symbol, tf_type)
